// FieldRook native shell — paths + free-port discovery (M026, section 1).
//
// AppPaths mirrors backend/app/paths.py exactly: per-user data dir,
// logs dir, single-instance lock file. Env overrides always win.
// PortDiscovery implements the ALPHA port decision: FIELDROOK_PORT (or
// --port) is authoritative; the default 8000 falls back to free-port
// discovery instead of failing on a foreign listener.

using System.Net;
using System.Net.Sockets;
using System.Text.Json;

namespace FieldRook.Core.Infrastructure;

public static class AppPaths
{
    public const string AppName = "FieldRook";
    public const string ServerExeName = "FieldRook-Server.exe";
    public const int DefaultPort = 8000;

    public static string UserDataDir()
    {
        var localAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        if (!string.IsNullOrWhiteSpace(localAppData))
        {
            return Path.Combine(localAppData, AppName);
        }

        return Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".local", "share", AppName);
    }

    public static string LogsDir() => Path.Combine(UserDataDir(), "logs");
    public static string LockFile() => Path.Combine(UserDataDir(), "fieldrook.lock");
    public static string WebView2DataDir() => Path.Combine(UserDataDir(), "webview2");

    public static string DefaultDbPath()
    {
        var overridePath = Environment.GetEnvironmentVariable("FIELDROOK_DB_PATH");
        if (!string.IsNullOrWhiteSpace(overridePath))
        {
            return overridePath;
        }

        return Path.Combine(UserDataDir(), "fieldrook.db");
    }

    public static string DefaultDemoStateDir()
    {
        var overridePath = Environment.GetEnvironmentVariable("FIELDROOK_DEMO_STATE");
        if (!string.IsNullOrWhiteSpace(overridePath))
        {
            return overridePath;
        }

        return Path.Combine(UserDataDir(), "demo-state");
    }

    /// <summary>Read the lock file; null when absent or corrupt (stale).</summary>
    public static InstanceLock? ReadLock()
    {
        try
        {
            var text = File.ReadAllText(LockFile());
            var lockData = JsonSerializer.Deserialize<InstanceLock>(text);
            return lockData is { Pid: > 0, Port: > 0 } ? lockData : null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    public static void WriteLock(int pid, int port)
    {
        Directory.CreateDirectory(UserDataDir());
        var payload = JsonSerializer.Serialize(new InstanceLock(pid, port, "fieldrook-api"));
        File.WriteAllText(LockFile(), payload);
    }

    public static void RemoveOwnLock(int pid)
    {
        var current = ReadLock();
        if (current is not null && current.Pid == pid)
        {
            try
            {
                File.Delete(LockFile());
            }
            catch (IOException)
            {
                // Best effort: a stale lock is cleared on next start.
            }
        }
    }

    /// <summary>Last lines of a log file for crash dialogs. Never throws.</summary>
    public static IReadOnlyList<string> TailLog(string path, int maxLines = 30)
    {
        try
        {
            if (!File.Exists(path))
            {
                return ["(no log file was found at " + path + ")"];
            }

            var lines = File.ReadAllLines(path);
            return lines.Length <= maxLines ? lines : lines[^maxLines..];
        }
        catch (Exception ex)
        {
            return [$"(could not read log: {ex.Message})"];
        }
    }
}

public sealed record InstanceLock(int Pid, int Port, string Service);

public static class PortDiscovery
{
    /// <summary>True when something accepts TCP on 127.0.0.1:port.</summary>
    public static bool IsPortInUse(int port, int timeoutMs = 1000)
    {
        using var client = new TcpClient();
        try
        {
            var task = client.ConnectAsync(IPAddress.Loopback, port);
            return task.Wait(timeoutMs) && client.Connected;
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>Ask the OS for a free loopback port (bind :0, read, release).</summary>
    public static int FindFreePort()
    {
        using var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        return ((IPEndPoint)listener.LocalEndpoint).Port;
    }

    /// <summary>
    /// Resolve the listen port. An explicit port (--port / FIELDROOK_PORT)
    /// is authoritative and never silently replaced; the default 8000
    /// discovers a free port when occupied, so a foreign listener does
    /// not brick the app out of the box.
    /// </summary>
    public static (int Port, bool Discovered) ResolvePort(int? explicitPort)
    {
        if (explicitPort is { } wanted)
        {
            if (wanted is < 1 or > 65535)
            {
                throw new ArgumentOutOfRangeException(nameof(explicitPort), "Expected 1-65535.");
            }

            return (wanted, false);
        }

        if (!IsPortInUse(AppPaths.DefaultPort))
        {
            return (AppPaths.DefaultPort, false);
        }

        return (FindFreePort(), true);
    }

    public static int? ExplicitPortFromArgs(string[] args, Func<string, string?> getEnv)
    {
        for (var i = 0; i < args.Length; i++)
        {
            if (string.Equals(args[i], "--port", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Length &&
                int.TryParse(args[i + 1], out var parsed))
            {
                return parsed;
            }
        }

        var env = getEnv("FIELDROOK_PORT");
        if (!string.IsNullOrWhiteSpace(env) && int.TryParse(env.Trim(), out var fromEnv))
        {
            return fromEnv;
        }

        return null;
    }
}
