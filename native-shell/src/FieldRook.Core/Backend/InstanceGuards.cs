// FieldRook native shell — navigation + instance guards (M026, sections 1-2).
//
// NavigationGuard: the WebView2 host may only navigate to loopback. Any
// other target is blocked and logged — no silent browser fallback.
// InstanceEvaluator: pure single-instance decision mirroring the M025
// launcher protocol (lock file + TCP probe + /api/status identity).

namespace FieldRook.Core.Backend;

public static class NavigationGuard
{
    private static readonly HashSet<string> LoopbackHosts = new(StringComparer.OrdinalIgnoreCase)
    {
        "127.0.0.1",
        "localhost",
        "::1",
        "[::1]",
    };

    /// <summary>True only for http(s) loopback URLs (+ about:blank at init).</summary>
    public static bool IsAllowed(string? uri)
    {
        if (string.IsNullOrWhiteSpace(uri))
        {
            return false;
        }

        if (string.Equals(uri.Trim(), "about:blank", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (!Uri.TryCreate(uri, UriKind.Absolute, out var parsed))
        {
            return false;
        }

        if (parsed.Scheme != Uri.UriSchemeHttp && parsed.Scheme != Uri.UriSchemeHttps)
        {
            return false;
        }

        return LoopbackHosts.Contains(parsed.Host) || IsLoopbackIp(parsed.Host);
    }

    private static bool IsLoopbackIp(string host)
    {
        // Covers 127/8 literals the backend itself would refuse to bind, but
        // the shell must never navigate anywhere HTTP could exfiltrate to.
        if (System.Net.IPAddress.TryParse(host.Trim('[', ']'), out var ip))
        {
            return System.Net.IPAddress.IsLoopback(ip);
        }

        return false;
    }
}

public enum InstanceState
{
    /// <summary>Port is free and no live Desktop owns the machine: start.</summary>
    Ready,

    /// <summary>A live Desktop instance owns the machine: focus/explain, exit.</summary>
    AlreadyRunning,

    /// <summary>Port is taken by a non-Desktop listener: explain, exit.</summary>
    PortConflict,
}

public sealed record StatusIdentity(string Service, string Runtime, string Version)
{
    public static readonly StatusIdentity Empty = new(string.Empty, string.Empty, string.Empty);

    public bool IsDesktop => Service == "fieldrook-api" && Runtime == "desktop";
    public bool IsFieldRook => Service == "fieldrook-api";
}

public sealed record InstanceProbe(
    int RequestedPort,
    int LockPort,
    int LockPid,
    bool LockPidAlive,
    bool LockCmdlineMatchesServer,
    bool TcpOpen,
    StatusIdentity Identity);

public sealed record InstanceDecision(InstanceState State, string Detail);

public static class InstanceEvaluator
{
    /// <summary>
    /// Pure single-instance decision. Mirrors FieldRook-Launcher.ps1:
    /// a live Desktop on ANY port wins (single instance per machine);
    /// a FieldRook dev server or foreign listener on OUR port is a
    /// conflict; anything unreadable degrades to conflict/ready, never
    /// to "already running".
    /// </summary>
    public static InstanceDecision Evaluate(InstanceProbe probe)
    {
        if (probe.LockPort != probe.RequestedPort)
        {
            if (probe is { LockPort: > 0, LockPidAlive: true, LockCmdlineMatchesServer: true })
            {
                return new InstanceDecision(
                    InstanceState.AlreadyRunning,
                    $"FieldRook Desktop is already running on port {probe.LockPort} (single instance).");
            }
            // Otherwise the lock is stale; the TCP probe below is authoritative.
        }

        if (probe.TcpOpen)
        {
            if (probe.Identity.IsDesktop)
            {
                var version = string.IsNullOrWhiteSpace(probe.Identity.Version)
                    ? "unknown"
                    : probe.Identity.Version;
                return new InstanceDecision(
                    InstanceState.AlreadyRunning,
                    $"FieldRook is already running on port {probe.RequestedPort} (Desktop v{version}).");
            }

            if (probe.Identity.IsFieldRook)
            {
                var runtime = string.IsNullOrWhiteSpace(probe.Identity.Runtime)
                    ? "unknown (older than Desktop identity)"
                    : probe.Identity.Runtime;
                return new InstanceDecision(
                    InstanceState.PortConflict,
                    $"Port {probe.RequestedPort} is in use by a FieldRook development server " +
                    $"(runtime '{runtime}'), not the Desktop app. Stop it or start with --port <free-port>.");
            }

            return new InstanceDecision(
                InstanceState.PortConflict,
                $"Port {probe.RequestedPort} is in use by another application (not FieldRook). " +
                "Stop it or start with --port <free-port>.");
        }

        return new InstanceDecision(
            InstanceState.Ready,
            $"Ready: port {probe.RequestedPort} is free.");
    }
}
