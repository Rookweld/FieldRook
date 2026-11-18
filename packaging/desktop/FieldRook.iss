; FieldRook native Windows installer — M038.
; Compile only from a verified, frozen, version-matched bundle via Build-Installer.ps1.
; Installed binaries are per-user. Case data always lives outside {app}.
#ifndef BundleDir
  #error "BundleDir is required (pass /DBundleDir=...)"
#endif
#ifndef PackageVersion
  #error "PackageVersion is required (pass /DPackageVersion=...)"
#endif
#ifndef NumericVersion
  #error "NumericVersion is required (pass /DNumericVersion=...)"
#endif
#ifndef OutputDir
  #error "OutputDir is required (pass /DOutputDir=...)"
#endif
#ifndef IconPath
  #error "IconPath is required (pass /DIconPath=...)"
#endif

[Setup]
; Stable upgrade/uninstall identity — never change between FieldRook releases.
AppId={{8A7EAFA3-3BD4-4DA1-82F3-885D214F92D1}
AppName=FieldRook
AppVersion={#PackageVersion}
AppVerName=FieldRook {#PackageVersion}
VersionInfoVersion={#NumericVersion}
AppPublisher=ROOKWELD
AppPublisherURL=https://rookweld.com
AppSupportURL=https://rookweld.com
DefaultDirName={localappdata}\Programs\FieldRook
DefaultGroupName=FieldRook
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir={#OutputDir}
OutputBaseFilename=FieldRook-Setup-{#PackageVersion}
SetupIconFile={#IconPath}
UninstallDisplayIcon={app}\FieldRook.exe
UsePreviousAppDir=yes
AppMutex=Global\FieldRookDesktopM026
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; The installer never packages the development checkout, .env, databases or logs.
Source: "{#BundleDir}\FieldRook.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\server\*"; DestDir: "{app}\server"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BundleDir}\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\FieldRook"; Filename: "{app}\FieldRook.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\FieldRook"; Filename: "{app}\FieldRook.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\FieldRook.exe"; Description: "Launch FieldRook"; Flags: nowait postinstall skipifsilent

; No UninstallDelete for {localappdata}\FieldRook: investigations, database,
; settings, demo state, logs and WebView2 profile remain the user's property.
