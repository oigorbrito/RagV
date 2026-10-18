#ifndef MyAppVersion
  #define MyAppVersion "0.1.1-hml"
#endif
#ifndef SourceSha
  #define SourceSha "a414b2a"
#endif
#define MyAppName "RagV Homologação"
#define MyAppPublisher "RagV / Grupo Villela"
#define MyAppExeName "RagVDesktop.exe"
#define ProjectDir "{localappdata}\RagV-Homologacao\project"

[Setup]
AppId={{F65B9E80-196B-4D04-A71E-962B3E891E45}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\RagV Homologacao
UsePreviousAppDir=no
DisableDirPage=no
DefaultGroupName=RagV Homologação
OutputDir=..\..\dist-installer
OutputBaseFilename=RagVDesktop-Homologacao-{#MyAppVersion}-{#SourceSha}-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\RagVDesktop.exe
WizardStyle=modern

[Files]
Source: "..\..\dist\RagVDesktop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "start-homologacao.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "configurar-datajud.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "copiar-token.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\_homologation-payload\project\*"; DestDir: "{#ProjectDir}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "HOMOLOGACAO.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RagV Homologação"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\start-homologacao.ps1"""; WorkingDir: "{app}"
Name: "{autoprograms}\Configurar DataJud - RagV Homologação"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\configurar-datajud.ps1"""; WorkingDir: "{app}"

[Icons]
Name: "{autoprograms}\Copiar token - RagV Homologação"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\copiar-token.ps1"""; WorkingDir: "{app}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\start-homologacao.ps1"""; Description: "Abrir RagV Homologação"; Flags: postinstall skipifsilent unchecked

; Perfil exclusivo: não lê nem altera RagVDesktop/config.ini da instalação habitual.
; Desinstalação preserva dados do perfil e não executa operações Docker.
