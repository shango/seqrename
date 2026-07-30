; Inno Setup script for SeqRename.
;
; Builds a per-user installer: PrivilegesRequired=lowest means no elevation and
; no UAC prompt, and {autopf} then resolves to %LOCALAPPDATA%\Programs, so this
; installs on a locked-down or networked workstation without admin rights.
; Pass /ALLUSERS on the command line to install machine-wide instead (that one
; does need admin).
;
; Compiled by build.ps1 -Installer, which passes the version in:
;   ISCC.exe /DAppVersion=0.3.0 packaging\SeqRename.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "SeqRename"
#define AppExe "SeqRename.exe"
#define AppPublisher "SeqRename"
#define AppUrl "https://github.com/shango/seqrename"

[Setup]
; Keep this GUID stable so upgrades replace an existing install.
AppId={{7B3C1E24-9A6F-4B58-8E31-2C5D0F7A4E91}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}

; No admin rights, no UAC. This is the whole point of the installer.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}

OutputDir={#SourcePath}\..\dist
OutputBaseFilename={#AppName}-{#AppVersion}-setup
SetupIconFile={#SourcePath}\seqrename.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Offer to close a running copy rather than failing on locked DLLs.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourcePath}\..\dist\{#AppName}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller's folder is removed by the uninstaller, but Qt may leave empty
; plugin directories behind.
Type: dirifempty; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"
