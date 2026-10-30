// FieldRook native shell — single-instance probe runner (M026, section 1).
//
// IO half of the M025 protocol: lock file + TCP probe + /api/status
// identity, decided by the pure InstanceEvaluator in FieldRook.Core.

using FieldRook.Core.Backend;
using FieldRook.Core.Infrastructure;

namespace FieldRook.Backend;

public static class InstanceProbeRunner
{
    /// <summary>
    /// ALPHA port decision: an explicit port (--port / FIELDROOK_PORT) is
    /// authoritative; the default 8000 is kept when free OR when a live
    /// Desktop answers on it (so the probe reports "already running");
    /// a foreign listener on 8000 triggers free-port discovery.
    /// </summary>
    public static async Task<(int Port, bool Discovered)> ResolveAppPortAsync(int? explicitPort)
    {
        if (explicitPort is not null)
        {
            return PortDiscovery.ResolvePort(explicitPort);
        }

        if (!PortDiscovery.IsPortInUse(AppPaths.DefaultPort))
        {
            return (AppPaths.DefaultPort, false);
        }

        if ((await BackendManager.GetStatusIdentityAsync(AppPaths.DefaultPort).ConfigureAwait(false)).IsDesktop)
        {
            return (AppPaths.DefaultPort, false);
        }

        return (PortDiscovery.FindFreePort(), true);
    }

    public static async Task<InstanceDecision> ProbeAsync(int port, string serverExeName)
    {
        var lockData = AppPaths.ReadLock();
        var lockPort = lockData?.Port ?? 0;
        var lockPid = lockData?.Pid ?? 0;
        var alive = ProcessFence.PidAlive(lockPid);
        var cmdline = alive ? ProcessFence.TryGetCommandLine(lockPid) : null;
        var matches = cmdline is not null &&
            cmdline.Contains(serverExeName, StringComparison.OrdinalIgnoreCase);

        var tcpOpen = PortDiscovery.IsPortInUse(port);
        var identity = tcpOpen
            ? await BackendManager.GetStatusIdentityAsync(port).ConfigureAwait(false)
            : StatusIdentity.Empty;

        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            port, lockPort, lockPid, alive, matches, tcpOpen, identity));

        if (decision.State == InstanceState.Ready && lockData is not null)
        {
            // Port is free: any lock is stale (previous crash/kill). Clear it.
            try
            {
                File.Delete(AppPaths.LockFile());
                AppLogger.Info($"Removed stale lock (pid {lockData.Pid}, port {lockData.Port}).");
            }
            catch (Exception ex)
            {
                AppLogger.Warn($"Could not clear stale lock: {ex.Message}");
            }
        }

        return decision;
    }
}
