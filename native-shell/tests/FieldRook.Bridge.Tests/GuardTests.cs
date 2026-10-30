// FieldRook native shell — guard contract tests (M026, sections 1-2).
//
// Navigation must stay on loopback; single-instance decisions mirror the
// M025 launcher protocol (lock + TCP probe + /api/status identity).

using FieldRook.Core.Backend;
using FieldRook.Core.Infrastructure;
using Xunit;

namespace FieldRook.Bridge.Tests;

public sealed class GuardTests
{
    [Theory]
    [InlineData("http://127.0.0.1:8000/", true)]
    [InlineData("http://127.0.0.1:54321/api/status", true)]
    [InlineData("http://localhost:8000/", true)]
    [InlineData("http://[::1]:8000/", true)]
    [InlineData("https://127.0.0.1:8000/", true)]
    [InlineData("about:blank", true)]
    [InlineData("http://evil.example.com/", false)]
    [InlineData("https://127.0.0.1.evil.example.com/", false)]
    [InlineData("http://192.168.1.10:8000/", false)]
    [InlineData("http://10.0.0.5/", false)]
    [InlineData("file:///C:/Windows/win.ini", false)]
    [InlineData("file://server/share/x.zip", false)]
    [InlineData("data:text/html,<h1>x</h1>", false)]
    [InlineData("javascript:alert(1)", false)]
    [InlineData("", false)]
    [InlineData(null, false)]
    [InlineData("not a uri", false)]
    public void NavigationGuard_AllowsLoopbackOnly(string? uri, bool expected)
    {
        Assert.Equal(expected, NavigationGuard.IsAllowed(uri));
    }

    [Fact]
    public void Instance_FreePort_IsReady()
    {
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8000, LockPort: 0, LockPid: 0,
            LockPidAlive: false, LockCmdlineMatchesServer: false,
            TcpOpen: false, Identity: StatusIdentity.Empty));

        Assert.Equal(InstanceState.Ready, decision.State);
    }

    [Fact]
    public void Instance_DesktopOnPort_IsAlreadyRunning()
    {
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8000, LockPort: 8000, LockPid: 1234,
            LockPidAlive: true, LockCmdlineMatchesServer: true,
            TcpOpen: true, Identity: new StatusIdentity("fieldrook-api", "desktop", "0.5.0")));

        Assert.Equal(InstanceState.AlreadyRunning, decision.State);
        Assert.Contains("0.5.0", decision.Detail);
    }

    [Fact]
    public void Instance_DesktopOnOtherPort_IsAlreadyRunning()
    {
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8001, LockPort: 8000, LockPid: 1234,
            LockPidAlive: true, LockCmdlineMatchesServer: true,
            TcpOpen: false, Identity: StatusIdentity.Empty));

        Assert.Equal(InstanceState.AlreadyRunning, decision.State);
    }

    [Fact]
    public void Instance_StaleLockOnOtherPort_IsReady()
    {
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8001, LockPort: 8000, LockPid: 999999,
            LockPidAlive: false, LockCmdlineMatchesServer: false,
            TcpOpen: false, Identity: StatusIdentity.Empty));

        Assert.Equal(InstanceState.Ready, decision.State);
    }

    [Fact]
    public void Instance_DevServerOnPort_IsConflict()
    {
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8000, LockPort: 0, LockPid: 0,
            LockPidAlive: false, LockCmdlineMatchesServer: false,
            TcpOpen: true, Identity: new StatusIdentity("fieldrook-api", "dev", "0.4.0")));

        Assert.Equal(InstanceState.PortConflict, decision.State);
        Assert.Contains("development server", decision.Detail);
    }

    [Fact]
    public void Instance_ForeignListener_IsConflict()
    {
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8000, LockPort: 0, LockPid: 0,
            LockPidAlive: false, LockCmdlineMatchesServer: false,
            TcpOpen: true, Identity: StatusIdentity.Empty));

        Assert.Equal(InstanceState.PortConflict, decision.State);
    }

    [Fact]
    public void Instance_UnreadableStatus_NeverCountsAsDesktop()
    {
        // Empty identity with an open port degrades to conflict, never "already".
        var decision = InstanceEvaluator.Evaluate(new InstanceProbe(
            RequestedPort: 8000, LockPort: 8000, LockPid: 1234,
            LockPidAlive: true, LockCmdlineMatchesServer: true,
            TcpOpen: true, Identity: StatusIdentity.Empty));

        Assert.Equal(InstanceState.PortConflict, decision.State);
    }

    [Fact]
    public void ExplicitPort_ParsesArgsThenEnv()
    {
        Assert.Equal(8123, PortDiscovery.ExplicitPortFromArgs(["--port", "8123"], _ => null));
        Assert.Equal(9000, PortDiscovery.ExplicitPortFromArgs([], name => name == "FIELDROOK_PORT" ? "9000" : null));
        Assert.Null(PortDiscovery.ExplicitPortFromArgs([], _ => null));
    }

    [Fact]
    public void ResolvePort_HonorsExplicit_AndFindsFreeDefault()
    {
        var (port, discovered) = PortDiscovery.ResolvePort(8123);
        Assert.Equal(8123, port);
        Assert.False(discovered);

        var (auto, _) = PortDiscovery.ResolvePort(null);
        Assert.InRange(auto, 1, 65535);

        Assert.Throws<ArgumentOutOfRangeException>(() => PortDiscovery.ResolvePort(70000));
    }

    [Fact]
    public void AppPaths_RespectsLocalAppDataOverride()
    {
        var temp = Path.Combine(Path.GetTempPath(), $"fr-paths-{Guid.NewGuid():N}");
        var original = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        Environment.SetEnvironmentVariable("LOCALAPPDATA", temp);
        try
        {
            Assert.Equal(Path.Combine(temp, "FieldRook"), AppPaths.UserDataDir());
            Assert.EndsWith("fieldrook.lock", AppPaths.LockFile());
        }
        finally
        {
            Environment.SetEnvironmentVariable("LOCALAPPDATA", original);
        }
    }
}
