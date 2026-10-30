// FieldRook native shell — startup (M026 contracts, sections 1-2, 6).
//
// Flow: parse args -> resolve port -> single-instance probe ->
// spawn + health-check the packaged backend -> show the WebView2 window.
// --smoke runs the same lifecycle headlessly (spawn/health/shutdown,
// no window) for CI verification.

using System.Runtime.InteropServices;
using System.Windows;
using FieldRook.Backend;
using FieldRook.Core.Backend;
using FieldRook.Core.Infrastructure;

namespace FieldRook;

public partial class App : Application
{
    private const string MutexName = @"Global\FieldRookDesktopM026";
    private const int AttachParentProcess = -1;

    private BackendManager? _backend;
    private Mutex? _mutex;

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachConsole(int processId);

    private async void OnStartup(object sender, StartupEventArgs e)
    {
        var args = e.Args;
        if (HasFlag(args, "--help", "-h"))
        {
            AttachConsole(AttachParentProcess);
            Console.WriteLine(Usage);
            Shutdown(0);
            return;
        }

        var allowDev = HasFlag(args, "--dev-backend") ||
            string.Equals(Environment.GetEnvironmentVariable("FIELDROOK_SHELL_DEV"), "1", StringComparison.Ordinal);
        var waitSeconds = FlagValue(args, "--wait-seconds", 90);
        int? explicitPort;
        try
        {
            explicitPort = PortDiscovery.ExplicitPortFromArgs(args, Environment.GetEnvironmentVariable);
            if (explicitPort is < 1 or > 65535)
            {
                throw new ArgumentOutOfRangeException(nameof(explicitPort));
            }
        }
        catch (Exception)
        {
            await FailAsync("Invalid port (expected 1-65535 via --port or FIELDROOK_PORT).", null, args)
                .ConfigureAwait(true);
            return;
        }

        if (HasFlag(args, "--smoke"))
        {
            AttachConsole(AttachParentProcess);
            var code = await RunSmokeAsync(explicitPort, waitSeconds, allowDev).ConfigureAwait(true);
            Shutdown(code);
            return;
        }

        // Supplemental race guard: the lock/probe/identity decision stays
        // authoritative; the mutex only sharpens a double-launch race.
        _mutex = new Mutex(initiallyOwned: true, MutexName, out var fresh);
        if (!fresh)
        {
            var (port, _) = await InstanceProbeRunner.ResolveAppPortAsync(explicitPort).ConfigureAwait(true);
            var decision = await InstanceProbeRunner.ProbeAsync(port, AppPaths.ServerExeName).ConfigureAwait(true);
            var detail = decision.State == InstanceState.Ready
                ? "Another FieldRook window is starting; please wait a moment and try again."
                : decision.Detail;
            AppLogger.Warn($"Second launch refused: {detail}");
            MessageBox.Show(detail, "FieldRook is already running", MessageBoxButton.OK, MessageBoxImage.Information);
            Shutdown(0);
            return;
        }

        try
        {
            var (port, discovered) = await InstanceProbeRunner.ResolveAppPortAsync(explicitPort).ConfigureAwait(true);
            if (discovered)
            {
                AppLogger.Info($"Port {AppPaths.DefaultPort} was occupied; discovered free port {port}.");
            }

            var decision = await InstanceProbeRunner.ProbeAsync(port, AppPaths.ServerExeName).ConfigureAwait(true);
            if (decision.State != InstanceState.Ready)
            {
                AppLogger.Warn($"Startup refused: {decision.Detail}");
                MessageBox.Show(
                    decision.Detail,
                    decision.State == InstanceState.AlreadyRunning ? "FieldRook is already running" : "FieldRook cannot start",
                    MessageBoxButton.OK,
                    decision.State == InstanceState.AlreadyRunning ? MessageBoxImage.Information : MessageBoxImage.Warning);
                Shutdown(decision.State == InstanceState.AlreadyRunning ? 0 : 2);
                return;
            }

            var spec = BackendSpec.Resolve(AppContext.BaseDirectory, allowDev);
            _backend = new BackendManager(spec, port);
            _backend.Start();
            try
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(waitSeconds + 5));
                await _backend.WaitForHealthyAsync(waitSeconds, cts.Token).ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                var tail = string.Join(Environment.NewLine, AppPaths.TailLog(_backend.ServerErrLog));
                _backend.Shutdown();
                _backend.Dispose();
                _backend = null;
                AppLogger.Error($"Backend failed to start: {ex.Message}");
                MessageBox.Show(
                    $"FieldRook could not start its backend service.{Environment.NewLine}{Environment.NewLine}" +
                    $"{ex.Message}{Environment.NewLine}{Environment.NewLine}--- server log ---{Environment.NewLine}{tail}",
                    "FieldRook backend failed to start",
                    MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown(1);
                return;
            }

            MainWindow = new MainWindow(_backend, port);
            MainWindow.Show();
        }
        catch (Exception ex)
        {
            await FailAsync($"FieldRook could not start: {ex.Message}", null, args).ConfigureAwait(true);
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _backend?.Dispose();
        _backend = null;
        _mutex?.Dispose();
        _mutex = null;
        base.OnExit(e);
    }

    /// <summary>
    /// Headless lifecycle check: probe -> spawn -> health -> shutdown.
    /// Prints one result line; exit 0 only on a clean round trip.
    /// </summary>
    private static async Task<int> RunSmokeAsync(int? explicitPort, int waitSeconds, bool allowDev)
    {
        try
        {
            var (port, discovered) = await InstanceProbeRunner.ResolveAppPortAsync(explicitPort).ConfigureAwait(false);
            var decision = await InstanceProbeRunner.ProbeAsync(port, AppPaths.ServerExeName).ConfigureAwait(false);
            if (decision.State != InstanceState.Ready)
            {
                Console.WriteLine($"SMOKE REFUSED ({decision.State}): {decision.Detail}");
                return decision.State == InstanceState.AlreadyRunning ? 3 : 2;
            }

            var spec = BackendSpec.Resolve(AppContext.BaseDirectory, allowDev);
            using var backend = new BackendManager(spec, port);
            backend.Start();
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(waitSeconds + 5));
            var identity = await backend.WaitForHealthyAsync(waitSeconds, cts.Token).ConfigureAwait(false);
            Console.WriteLine(
                $"SMOKE OK: pid={backend.ChildPid} port={port} discovered={discovered} " +
                $"service={identity.Service} runtime={identity.Runtime} version={identity.Version}");
            return 0;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"SMOKE FAIL: {ex.GetType().Name}: {ex.Message}");
            return 1;
        }
    }

    private Task FailAsync(string message, string? logTail, string[] args)
    {
        AppLogger.Error(message);
        if (HasFlag(args, "--smoke"))
        {
            Console.WriteLine($"SMOKE FAIL: {message}");
        }
        else
        {
            MessageBox.Show(message, "FieldRook", MessageBoxButton.OK, MessageBoxImage.Error);
        }

        Shutdown(1);
        return Task.CompletedTask;
    }

    private static bool HasFlag(string[] args, params string[] names)
    {
        return args.Any(a => names.Contains(a, StringComparer.OrdinalIgnoreCase));
    }

    private static int FlagValue(string[] args, string name, int fallback)
    {
        for (var i = 0; i + 1 < args.Length; i++)
        {
            if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase) &&
                int.TryParse(args[i + 1], out var value) && value > 0)
            {
                return value;
            }
        }

        return fallback;
    }

    private const string Usage = """
        FieldRook Desktop (M026 native shell).
        Usage: FieldRook.exe [--port N] [--wait-seconds N] [--dev-backend] [--smoke]
          --port N         Listen port (default 8000; FIELDROOK_PORT also honored).
                           The default dodges foreign listeners via free-port
                           discovery; an explicit port is never replaced.
          --wait-seconds N Backend health budget (default 90).
          --dev-backend    Accept runtime "dev" in health (verification only).
          --smoke          Headless lifecycle check (spawn/health/shutdown).
        Dev overrides: FIELDROOK_SERVER_EXE + FIELDROOK_SERVER_ARGS,
                       FIELDROOK_SHELL_DEV=1, FIELDROOK_DB_PATH, FIELDROOK_DEMO_STATE.
        """;
}
