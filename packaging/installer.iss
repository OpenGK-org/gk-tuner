#ifndef AppVersion
  #error AppVersion must be supplied by tools.build_release
#endif
#ifndef BuildRoot
  #error BuildRoot must be supplied by tools.build_release
#endif
#ifndef ReleaseDir
  #error ReleaseDir must be supplied by tools.build_release
#endif
[Setup]
AppId={{317DB0EA-E901-48EA-AE3E-8197C9D100A5}
AppName=GK Tuner
AppVersion={#AppVersion}
AppVerName=GK Tuner {#AppVersion} Preview
AppPublisher=OpenGK
DefaultDirName={localappdata}\Programs\GK Tuner
DefaultGroupName=GK Tuner
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=GK-Tuner-{#AppVersion}-Setup-x64
SetupIconFile={#SourcePath}..\gktuner\assets\opengk.ico
UninstallDisplayIcon={app}\GK Tuner.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
InfoAfterFile={#SourcePath}TESTER-README.txt
VersionInfoVersion={#AppVersion}
VersionInfoDescription=GK Tuner Windows installer

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#BuildRoot}\GK Tuner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GK Tuner"; Filename: "{app}\GK Tuner.exe"; WorkingDir: "{localappdata}\GK Tuner"; AppUserModelID: "OpenGK.GKTuner"
Name: "{autodesktop}\GK Tuner"; Filename: "{app}\GK Tuner.exe"; WorkingDir: "{localappdata}\GK Tuner"; Tasks: desktopicon; AppUserModelID: "OpenGK.GKTuner"
Name: "{group}\Uninstall GK Tuner"; Filename: "{uninstallexe}"

[Dirs]
Name: "{localappdata}\GK Tuner"

[Run]
Filename: "{app}\GK Tuner.exe"; Description: "Launch GK Tuner"; Flags: nowait postinstall skipifsilent
