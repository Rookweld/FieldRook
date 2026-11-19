# M039 — First Real Installation & Acceptance

Branch: `m039/first-install-acceptance`
Base: M038 local rc.3 commit `05569a5`
Fixed candidate: **0.6.0-rc.4** (local, unsigned; not published)

## Failure discovered on a real Windows installation
The original unsigned `0.6.0-rc.3` setup was built correctly, but a first install
while a portable `rc.2` was running returned **exit 1**:
> Setup has detected that FieldRook is currently running.

Root cause: the Inno `AppMutex=Global\FieldRookDesktopM026` setting checked a
**machine-wide** mutex created by any portable FieldRook, even from a different
directory. This blocked unrelated first installs. Automatic application-closing
was explicitly **disabled** during testing, and the original rc.2 process was
not stopped, killed or modified.

## Fix
Remove the installation-wide `AppMutex` declaration from `FieldRook.iss`.
Retain `CloseApplications=yes` and Inno Restart Manager's handling of
**installed application files that are actually in use**.

The application still has its separate single-instance protection for runtime.
Portable and installed copies cannot be run as two independent GUI instances in
the same Windows session without changing that runtime model. The installer
may run beside an existing portable copy, but the portable copy should be
closed before starting the newly installed app interactively.

## Initial isolated on-device findings (corrected internal rc.3 installer)
- Actual first per-user install to a disposable folder: **PASS, exit 0**.
- Windows Start Menu shortcut and uninstall registry entry: **PASS**.
- Installed self-contained WPF exe version: **0.6.0-rc.3**, correct.
- Installed app headless lifecycle `--smoke`: **PASS, exit 0**, with distinct port
  and local data root, without disturbing portable rc.2.
- In-place reinstall of same internal build: **PASS**.
- Actual uninstall: **PASS**; program files, Start Menu link and Windows
  installed-app registry entry removed.
- Isolated `keep-this-case.txt` marker in user-data test folder: **PRESERVED**.
- Original portable rc.2 process remained running and untouched.

The internal probe installer was strictly for diagnosing the bug. It is NOT a
public asset and must not be confused with the original broken rc.3 setup.

## Repeatable test automation
`packaging/desktop/Test-Installer.ps1` performs the same acceptance sequence
using a disposable program directory and isolated runtime data. It refuses
to replace any existing registered FieldRook installation, checks all installed
payload components, checks the Start Menu, uses an independent loopback port,
then reinstalls and uninstalls safely. It does not delete case data and will not
deliberately kill unrelated FieldRook processes.

Example (on the Windows build host):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\desktop\Test-Installer.ps1 `
  -InstallerPath .\packaging\desktop\dist\m039-local\FieldRook-Setup-0.6.0-rc.4.exe `
  -Version 0.6.0-rc.4
```

## Verification boundaries / external acceptance still outstanding
- Installation/reinstallation of **the same version** is not the same as a
  tested real upgrade from a prior installed version.
- True native GUI, WebView2 rendering, accessibility keyboard flow,
  missing-WebView2 experience, actual user data migrations, antivirus
  reputation and SmartScreen behavior must be tested on a clean Windows
  10/11 machine under a real tester account before distribution.
- Installer remains unsigned. Do not instruct technicians to bypass
  organization security policy or SmartScreen.
- The large regression suite remains deferred per user instruction.
- No push, signing or publication is performed by these local tests.
