# Windows Service Recovery Checks

A calm order for looking at a service that stopped or will not start.
This note describes states and recovery habits. It is background
reading, not a diagnosis of any single machine.

## Service States and Startup Types

A service reports a state such as running, stopped, or paused, plus a
startup type such as automatic, manual, or disabled. Read both values
together. A stopped service with automatic startup tells a different
story than a stopped service that was left on manual.

Check the last state change time when it is available. A fresh stop
after a long healthy run points at a recent trigger. A service that
has never started points at setup or dependency trouble instead.

## Recovery Actions

Windows can restart a service on first, second, and later failures,
optionally running a program or rebooting the host. Review these
recovery actions before changing them. Aggressive restarts can hide a
repeat crash and fill logs faster than anyone can read them.

Note the reset counter and any restart delay. A short delay with many
restarts suggests flapping. A long delay with few attempts suggests a
single hard fault. Match the recovery pace to the evidence you see.

## Dependency Review

Many services need other services or drivers first. Open the
dependency list and walk it from the bottom up. A healthy top service
cannot stay up when a lower one is stopped or disabled.

Look for chains that cross team boundaries, such as a business app
that needs a database client and a network helper. Confirm each link
in turn rather than restarting the top item alone.

## Safe Restart Sequence

When a restart is appropriate, move in small steps. Confirm the
startup type, confirm dependencies, then start the service once and
watch the state settle. Collect the new state and any fresh events
before trying a second start.

If the service stops again within a minute, stop restarting and read
the surrounding logs. Repeat restarts without new evidence only add
noise. Hand off the exact timestamps and the recovery settings you
observed.
