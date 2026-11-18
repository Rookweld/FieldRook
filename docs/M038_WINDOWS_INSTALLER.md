# M038 — Windows Installation & Distribution

**Local branch:** `m038/installation-distribution`
**Candidate version:** `0.6.0-rc.3`
**Base:** M037 (`e20dee5`)

## For a technician installing FieldRook

Use **FieldRook-Setup-0.6.0-rc.3.exe** (Windows 10/11 x64).

- Installs without administrator rights to `%LOCALAPPDATA%\Programs\FieldRook`.
- Registers **FieldRook** in the current user's Start menu and in Windows installed apps.
- Offers an optional desktop shortcut (off by default).
- Starts `FieldRook.exe` at the end if the user elects to run it.
- Includes the WPF/WebView2 desktop shell and frozen Python service, demo worker and frontend. No Python, Node, .NET SDK or development tools needed.
- **Microsoft Edge WebView2 Runtime is required**, and must be installed independently if missing. The native shell explains this at startup; the installer does not silently download anything.
- Unsigned development candidate: Windows SmartScreen or organizational security software may warn. Do not bypass security policy to install it on managed devices.
- Does not install a background Windows service, scheduled task or startup entry. The app owns its local server and stops it on exit.

### Upgrade and uninstall

- Close FieldRook, then run the newer Setup executable. The stable Inno `AppId` reuses the same application entry and install path.
- The application checks its process mutex, and the setup flow has app-close handling enabled.
- Windows Settings > Apps > Installed apps > FieldRook > Uninstall removes **installed program files and shortcuts**.
- **The user's investigation database, case evidence, settings and logs stay in `%LOCALAPPDATA%\FieldRook`**. The installer/uninstaller does not clear that folder.
- To *deliberately* delete all personal data, make sure FieldRook is closed, back up what you need, and remove `%LOCALAPPDATA%\FieldRook` manually. This is not part of ordinary uninstall.

### Portable alternative

`FieldRook-0.6.0-rc.3.zip` remains an alternative: extract the entire folder and launch `FieldRook.exe`. Do not run just the executable copied out of the ZIP; it needs the adjacent `server` folder. The portable ZIP registers nothing with Windows.

## For a developer creating a local installer candidate

On a Windows x64 build workstation with Python 3.12, the pinned requirements, Node/pnpm, .NET 10 SDK and **Inno Setup 6**:

```powershell
# Run from repository root, after committing the intended source:
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\desktop\Build-DesktopRelease.ps1
```

The orchestration script performs three strict steps:
1. `build.ps1` compiles frontend, freezes worker/server and creates a portable ZIP/BOM. It refuses a dirty checkout.
2. `Build-Shell.ps1` publishes the self-contained `win-x64` WPF executable and refreshes the ZIP/checksums.
3. `Build-Installer.ps1` validates the **actual bundle** (shell, server, worker, frontend), its version stamps and the Git commit in the BOM before invoking Inno Setup.

The default destination is `packaging\desktop\dist\m038-local` to avoid overwriting historical rc.2 assets.

Expected output:
```text
packaging/desktop/dist/m038-local/
  FieldRook-Setup-0.6.0-rc.3.exe     unsigned per-user Windows installer
  FieldRook-0.6.0-rc.3.zip           portable distribution
  FieldRook-0.6.0-rc.3/             expanded portable layout
  INSTALLER_SHA256.txt               hashes for Setup and ZIP
  INSTALLER_BUILD.txt                version, Git commit, provenance
  SHA256SUMS.txt, BOM.txt            frozen backend + native shell provenance
```

The Inno source is `FieldRook.iss`. Its permanent `AppId` **must not change** between versions. Program files are the only payload; user data is intentionally excluded. It does not sign binaries.

## Verification and release gates

**Fast checks:** Inno compilation, version and BOM identity, hashes, frozen server `--version`, preserved resource layout, and optional startup smoke in isolated local data.

**Not yet certified without a clean machine:** first install, WebView2 missing/reinstall, SmartScreen/Defender reputation, install directory ACLs, real upgrade from a previous installer, double launch, running-app upgrade, complete uninstall and data retention. Full regression and end-to-end UI checks remain deferred at the user's request.

**This is a local unsigned installation candidate, not a public release.** No Git push, tags, signing certificate or download link should be inferred.
