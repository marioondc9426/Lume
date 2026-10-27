; Instalador do Lume (Windows). Gerado no GitHub Actions depois do Lume.exe:
;   ISCC.exe /DMyAppVersion=4.0 installer\lume.iss      ->  dist\Lume-Setup.exe
; Instala so para o seu usuario (sem pedir administrador), cria atalhos e um desinstalador. Suas conversas e chaves ficam em
; %LOCALAPPDATA%\Lume e NAO sao apagadas ao desinstalar.
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif

[Setup]
AppId={{6B1F2D7A-3C4E-4F6B-9A7D-5E2C8B1D4F90}
AppName=Lume
AppVersion={#MyAppVersion}
AppPublisher=Lume
AppPublisherURL=https://github.com/marioondc9426/Lume
DefaultDirName={autopf}\Lume
DefaultGroupName=Lume
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Lume-Setup
SetupIconFile=..\build\lume.ico
UninstallDisplayIcon={app}\Lume.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Lume.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG-EN.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Lume"; Filename: "{app}\Lume.exe"
Name: "{autodesktop}\Lume"; Filename: "{app}\Lume.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Lume.exe"; Description: "{cm:LaunchProgram,Lume}"; Flags: nowait postinstall skipifsilent

[Messages]
brazilianportuguese.FinishedLabel=O Lume foi instalado. Suas conversas e chaves ficam em %LOCALAPPDATA%\Lume (não são apagadas ao desinstalar).
