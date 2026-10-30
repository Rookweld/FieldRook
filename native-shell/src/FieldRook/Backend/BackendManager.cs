// FieldRook native shell — backend lifecycle (M026 contracts, section 1).
//
// Spawns the packaged FieldRook-Server.exe as an application-owned child
// (loopback only), waits for /api/status identity health, and shuts down
// ONLY the owned child after a command-line fence check, then the demo
// worker via the server's --stop-demo-worker path. A Windows Job Object
// with KILL_ON_JOB_CLOSE guarantees no orphan backend even if the shell
// itself crashes.
//
// Dev overrides (verification only, never in the packaged layout):
//   FIELDROOK_SERVER_EXE  + FIELDROOK_SERVER_ARGS (e.g. python + entry)
//   --dev-backend / FIELDROOK_SHELL_DEV=1 accepts runtime "dev" in health.

using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using FieldRook.Core.Backend;
using FieldRook.Core.Infrastructure;

namespace FieldRook.Backend;

public sealed class BackendSpec
{
    public required string FileName { get; init; }
    public string Arguments { get; init; } = string.Empty;
    public required string FenceToken { get; init; }
    public bool AllowDevRuntime { get; init; }

    public string StopWorkerArguments =>
        string.IsNullOrWhiteSpace(Arguments) ? "--stop-demo-worker" : $"{Arguments} --stop-demo-worker";

    public static BackendSpec Resolve(string appDir, bool allowDevRuntime)
    {
        var overrideExe = Environment.GetEnvironmentVariable("FIELDROOK_SERVER_EXE");
        if (!string.IsNullOrWhiteSpace(overrideExe))
        {
            var args = Environment.GetEnvironmentVariable("FIELDROOK_SERVER_ARGS") ?? string.Empty;
            var token = args.Contains("fieldrook-server-entry", StringComparison.OrdinalIgnoreCase)
                ? "fieldrook-server-entry.py"
                : Path.GetFileName(overrideExe);
            return new BackendSpec { FileName = overrideExe, Arguments = args, FenceToken = token, AllowDevRuntime = allowDevRuntime };
        }

        return new BackendSpec
        {
            FileName = Path.Combine(appDir, "server", AppPaths.ServerExeName),
            FenceToken = AppPaths.ServerExeName,
            AllowDevRuntime = allowDevRuntime,
        };
    }
}

public sealed class BackendManager : IDisposable
{
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(5) };

    private readonly BackendSpec _spec;
    private readonly int _port;
    private Process? _child;
    private DateTime _childStartTime;
    private JobObject? _job;
    private bool _disposed;

    public BackendManager(BackendSpec spec, int port)
    {
        _spec = spec;
        _port = port;
    }

    public int ChildPid => _child?.Id ?? 0;
    public StatusIdentity LastIdentity { get; private set; } = StatusIdentity.Empty;
    public string ServerOutLog => Path.Combine(AppPaths.LogsDir(), "server.out.log");
    public string ServerErrLog => Path.Combine(AppPaths.LogsDir(), "server.err.log");

    public event EventHandler? ChildExited;

    public void Start()
    {
        if (!File.Exists(_spec.FileName))
        {
            throw new FileNotFoundException($"Server executable not found: {_spec.FileName}");
        }

        Directory.CreateDirectory(AppPaths.LogsDir());

        var psi = new ProcessStartInfo
        {
            FileName = _spec.FileName,
            Arguments = _spec.Arguments,
            WorkingDirectory = Path.GetDirectoryName(_spec.FileName) ?? AppContext.BaseDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        psi.Environment["FIELDROOK_PORT"] = _port.ToString();
        psi.Environment.TryAdd("FIELDROOK_DB_PATH", AppPaths.DefaultDbPath());
        psi.Environment.TryAdd("FIELDROOK_DEMO_STATE", AppPaths.DefaultDemoStateDir());

        var child = Process.Start(psi) ?? throw new InvalidOperationException("Failed to start the server process.");
        _child = child;
        _childStartTime = child.StartTime;
        AppLogger.Info($"Server starting (pid {child.Id}, port {_port}): {_spec.FileName} {_spec.Arguments}".Trim());

        // No-orphan backstop: the OS kills the child if WE die. Best effort:
        // nested-job hosts refuse assignment; the fenced kill still applies.
        _job = new JobObject();
        if (!_job.TryAssign(child))
        {
            AppLogger.Warn("Job-object assignment failed; shutdown relies on the fenced kill path.");
        }

        DrainToFile(child.StandardOutput, ServerOutLog);
        DrainToFile(child.StandardError, ServerErrLog);

        child.EnableRaisingEvents = true;
        child.Exited += (_, _) => ChildExited?.Invoke(this, EventArgs.Empty);

        AppPaths.WriteLock(child.Id, _port);
    }

    public async Task<StatusIdentity> WaitForHealthyAsync(int timeoutSeconds, CancellationToken ct)
    {
        var deadline = DateTime.UtcNow.AddSeconds(timeoutSeconds);
        while (DateTime.UtcNow < deadline)
        {
            ct.ThrowIfCancellationRequested();

            if (_child is not null && _child.HasExited)
            {
                throw new InvalidOperationException(
                    $"The server process exited during startup (code {_child.ExitCode}). See {ServerErrLog}.");
            }

            var identity = await GetStatusIdentityAsync(_port).ConfigureAwait(false);
            if (identity.IsFieldRook)
            {
                LastIdentity = identity;
                if (identity.Runtime == "desktop" || (_spec.AllowDevRuntime && identity.Runtime == "dev"))
                {
                    AppLogger.Info($"Backend healthy: service={identity.Service} runtime={identity.Runtime} v{identity.Version}");
                    return identity;
                }

                AppLogger.Warn($"Backend answered with unexpected runtime '{identity.Runtime}'; refusing.");
                throw new InvalidOperationException(
                    $"The backend on port {_port} reports runtime '{identity.Runtime}', not 'desktop'.");
            }

            await Task.Delay(TimeSpan.FromMilliseconds(500), ct).ConfigureAwait(false);
        }

        throw new TimeoutException($"The server did not become healthy within {timeoutSeconds}s. See {ServerErrLog}.");
    }

    /// <summary>
    /// Fenced shutdown: kill ONLY the owned child (cmdline + start-time
    /// must match), then the demo worker, then our lock. Never throws.
    /// </summary>
    public void Shutdown()
    {
        var child = _child;
        _child = null;
        if (child is null)
        {
            return;
        }

        var pid = child.Id;
        try
        {
            if (!child.HasExited)
            {
                if (FenceHolds(pid))
                {
                    child.Kill();
                    AppLogger.Info($"Stopped owned server pid {pid}.");
                    child.WaitForExit(5000);
                }
                else
                {
                    AppLogger.Error(
                        $"Refusing to kill pid {pid}: fence check failed (expected '{_spec.FenceToken}'). " +
                        "The job object reaps it on shell exit.");
                }
            }
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            AppLogger.Warn($"Server stop raced its exit (pid {pid}): {ex.Message}");
        }

        StopDemoWorker();
        AppPaths.RemoveOwnLock(pid);
        child.Dispose();
    }

    public static async Task<StatusIdentity> GetStatusIdentityAsync(int port)
    {
        try
        {
            using var response = await Http.GetAsync($"http://127.0.0.1:{port}/api/status").ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return StatusIdentity.Empty;
            }

            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync().ConfigureAwait(false));
            var root = doc.RootElement;
            return new StatusIdentity(
                GetString(root, "service"),
                GetString(root, "runtime"),
                GetString(root, "version"));
        }
        catch (Exception)
        {
            return StatusIdentity.Empty;
        }
    }

    private static string GetString(JsonElement root, string name)
    {
        return root.TryGetProperty(name, out var prop) && prop.ValueKind == JsonValueKind.String
            ? prop.GetString() ?? string.Empty
            : string.Empty;
    }

    private bool FenceHolds(int pid)
    {
        // Fence 1: same PID start time we recorded at spawn (kills PID-reuse).
        try
        {
            using var current = Process.GetProcessById(pid);
            if (current.StartTime != _childStartTime)
            {
                return false;
            }
        }
        catch (Exception)
        {
            return false; // Already gone (or unreadable): nothing to kill.
        }

        // Fence 2 (contract): the command line names our server.
        var cmdline = ProcessFence.TryGetCommandLine(pid);
        return cmdline is not null &&
            cmdline.Contains(_spec.FenceToken, StringComparison.OrdinalIgnoreCase);
    }

    private void StopDemoWorker()
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = _spec.FileName,
                Arguments = _spec.StopWorkerArguments,
                WorkingDirectory = Path.GetDirectoryName(_spec.FileName) ?? AppContext.BaseDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            using var stopper = Process.Start(psi);
            if (stopper is null)
            {
                return;
            }

            stopper.WaitForExit(15000);
            AppLogger.Info($"Demo worker shutdown: {stopper.StandardOutput.ReadToEnd().Trim()}");
        }
        catch (Exception ex)
        {
            AppLogger.Warn($"Demo worker shutdown failed (continuing): {ex.Message}");
        }
    }

    private static void DrainToFile(StreamReader reader, string path)
    {
        var writer = new StreamWriter(new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.Read))
        {
            AutoFlush = true,
        };
        Task.Run(async () =>
        {
            try
            {
                string? line;
                while ((line = await reader.ReadLineAsync().ConfigureAwait(false)) is not null)
                {
                    await writer.WriteLineAsync(line).ConfigureAwait(false);
                }
            }
            catch (Exception)
            {
                // Child gone; nothing left to drain.
            }
            finally
            {
                await writer.DisposeAsync().ConfigureAwait(false);
            }
        });
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        Shutdown();
        _job?.Dispose();
    }
}
