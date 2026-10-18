#ifndef MyAppVersion
  #define MyAppVersion "0.1.2-hml"
#endif
#ifndef SourceSha
  #define SourceSha "nao-identificado"
#endif
#define MyAppName "RagV Homologação"
#define MyAppPublisher "RagV / Grupo Villela"
#define ProjectDir "{app}\runtime"
#define PowerShellExe "{sys}\WindowsPowerShell\v1.0\powershell.exe"

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
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\RagVDesktop.exe
WizardStyle=modern

[Files]
Source: "..\..\dist\RagVDesktop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "start-homologacao.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "homologacao-common.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "configurar-datajud.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "copiar-token.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\_homologation-payload\project\*"; DestDir: "{#ProjectDir}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "HOMOLOGACAO.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RagV Homologação"; Filename: "{#PowerShellExe}"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\start-homologacao.ps1"""; WorkingDir: "{app}"
Name: "{autoprograms}\Configurar DataJud - RagV Homologação"; Filename: "{#PowerShellExe}"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\configurar-datajud.ps1"""; WorkingDir: "{app}"
Name: "{autoprograms}\Copiar token - RagV Homologação"; Filename: "{#PowerShellExe}"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\copiar-token.ps1"""; WorkingDir: "{app}"

[Run]
Filename: "{#PowerShellExe}"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\start-homologacao.ps1"""; Description: "Abrir RagV Homologação"; Flags: postinstall skipifsilent unchecked

; Sem registro de configuração compartilhado, seleção de checkout Git ou remoção Docker.
[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not FileExists(ExpandConstant('{app}\runtime\compose.yaml')) or
       not FileExists(ExpandConstant('{app}\runtime\HOMOLOGACAO.txt')) or
       not FileExists(ExpandConstant('{app}\runtime\scripts\bootstrap_homologation.py')) or
       not FileExists(ExpandConstant('{app}\homologacao-common.ps1')) then
      RaiseException('A instalação está incompleta. Não abra o aplicativo; reinstale o pacote de homologação.');
  end;
end;
