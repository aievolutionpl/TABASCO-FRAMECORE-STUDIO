#define AppVersion "0.3.0"
[Setup]
AppId={{238916F1-F4C2-4E34-A34C-586F66365001}
AppName=FrameCore Studio
AppVersion={#AppVersion}
AppPublisher=TABASCO CREATIVES + FRAMECORE
AppPublisherURL=https://github.com/aievolutionpl/TABASCO-FRAMECORE-STUDIO
DefaultDirName={localappdata}\Programs\FrameCore Studio
DefaultGroupName=FrameCore Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installers
OutputBaseFilename=FrameCore-Studio-{#AppVersion}-windows-x64-setup
SetupIconFile=generated\icon.ico
UninstallDisplayIcon={app}\FrameCoreStudio.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
CloseApplications=yes
[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Utwórz ikonę na pulpicie"; GroupDescription: "Skróty:"; Flags: unchecked
[Files]
Source: "..\dist\FrameCoreStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "generated\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
[Icons]
Name: "{autoprograms}\FrameCore Studio"; Filename: "{app}\FrameCoreStudio.exe"
Name: "{autodesktop}\FrameCore Studio"; Filename: "{app}\FrameCoreStudio.exe"; Tasks: desktopicon
[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Przygotowywanie okna aplikacji…"; Flags: waituntilterminated
Filename: "{app}\FrameCoreStudio.exe"; Description: "Uruchom FrameCore Studio"; Flags: nowait postinstall skipifsilent
; Projects live outside {app}; uninstall must not remove personal media or agent settings.
