# Application Launch Failures

What to check when a program will not start or exits silently. This
note walks through launch stages and simple evidence habits. It is
background reading, not a diagnosis of any single machine.

## Launch Stages

A launch moves from a shortcut or command to process creation, then
to early setup, then to a visible window. Note how far the attempt
gets. A brief hourglass with no process left behind differs from a
process that stays alive with no window.

Try the launch twice and watch for a short-lived process entry. A
process that appears and exits within seconds often wrote a log or
an event nearby. A launch that never creates a process points at the
path, the launcher, or a block before creation.

## Silent Exit Clues

Silent exits hide their reason in nearby records. Check the
application log, the system log, and any program-specific log folder
for entries stamped within the same minute. Copy the exact lines
rather than summarising them from memory.

Look for a companion dialog hidden behind other windows, and for a
tray icon that lingers after the window fails to open. Small traces
like these separate a true silent exit from a window drawn off
screen or on a missing display.

## Permission and Path Checks

Confirm the user can read and execute the program path, and that any
network or removable path is actually present. A shortcut that points
at a moved folder fails the same quiet way every time. Quote the full
resolved path in your notes.

Check for blocks that stop new processes, such as policy rules or an
overzealous guard that quarantines the launcher. A second launch from
a local path with a short name helps separate path trouble from
policy trouble.

## Next Evidence to Collect

Before changing settings, gather a small repeatable set: the exact
command or shortcut used, the process name you expected, whether a
process appeared, and the closest log lines by time. A two-minute
window around the attempt is usually enough.

Repeat the attempt once after collecting the baseline, so the second
run can be compared line by line. Stable clues across both runs are
worth carrying forward. One-off lines are worth noting but not
chasing alone.
