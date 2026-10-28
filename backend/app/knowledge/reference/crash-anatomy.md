# Crash Event Anatomy

How to read a Windows application crash record without overclaiming.
This note explains the usual fields and their limits. It is
background reading, not a diagnosis of any single machine.

## Event Log Fields

A crash entry usually carries an event identifier, a timestamp, the
application name, and a short message. Event 1000 in the application
log is a common carrier for process faults. Copy the identifier, the
time, and the application name exactly as shown.

Check whether the same application appears more than once. A single
isolated entry suggests a one-off trigger. A tight cluster of entries
with close timestamps suggests a repeatable path worth isolating.

## Faulting Module Reading

Many crash records name a faulting module and a fault offset. The
module is the binary where the fault was observed, which may be the
application itself or a library it loaded. The offset locates the
spot inside that binary for a developer to map later.

Treat the module as a pointer, not a verdict. A fault inside a shared
library can still be caused by bad input from the caller. Keep the
module name, version, and path together so the pattern stays clear.

## Exception Codes

An exception code such as `0xc0000005` classifies the kind of fault
that stopped the process. Access violations, illegal instructions,
and stack exhaustion each leave a different code. Record the literal
code and resist translating it into a cause on its own.

Compare the code across repeated crashes. A stable code with a stable
module points at one path. A shifting code across many modules points
at wider instability, such as memory pressure or a failing driver.

## Correlation Tips

Line up the crash time with nearby service, driver, and update
entries. A crash that follows an update or a driver reload by seconds
deserves a different theory than one that arrives alone at idle.

Gather the application version, the faulting module detail, and the
exception code into one short summary. That trio travels well to the
next reader and keeps the discussion tied to measured entries.
