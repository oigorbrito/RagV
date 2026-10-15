#define MyAppName "RagV Desktop"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "RagV"
#define MyAppExeName "RagVDesktop.exe"

[Setup]
AppId={{B65C2D92-5C34-4B84-93C1-3DB9D8C27A71}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\RagV Desktop
UsePreviousAppDir=no
DisableDirPage=no
DefaultGroupName=RagV Desktop
OutputDir=..\..\dist-installer
OutputBaseFilename=RagVDesktop-Setup-0.1.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\RagVDesktop.exe
WizardStyle=modern

[Files]
Source: "..\..\dist\RagVDesktop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "start-installed.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "start-installed-hidden.vbs"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RagV Desktop"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\start-installed-hidden.vbs"""; WorkingDir: "{app}"

[Run]
Filename: "{sys}\wscript.exe"; Parameters: """{app}\start-installed-hidden.vbs"""; Description: "Abrir RagV Desktop"; Flags: postinstall skipifsilent unchecked

[UninstallDelete]



[Code]
var
  ProjectPage: TInputDirWizardPage;

function ConfigFilePath: string;
begin
  Result := ExpandConstant('{localappdata}\RagVDesktop\config.ini');
end;

function ReadProjectPath: string;
var
  ConfigPath: string;
begin
  ConfigPath := ConfigFilePath;
  Result := GetIniString('Desktop', 'ProjectPath', '', ConfigPath);
end;

procedure InitializeWizard;
var
  ExistingPath: string;
begin
  ProjectPage := CreateInputDirPage(
    wpSelectDir,
    'Projeto RagV',
    'Selecione a pasta do projeto Docker',
    'Escolha a pasta que contem o arquivo compose.yaml.',
    False,
    ''
  );

  ProjectPage.Add('Pasta do projeto:');

  ExistingPath := ReadProjectPath;

  if ExistingPath <> '' then
    ProjectPage.Values[0] := ExistingPath
  else
    ProjectPage.Values[0] := ExpandConstant('{userdocs}\RagV');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ProjectPath: string;
begin
  Result := True;

  if CurPageID = ProjectPage.ID then
  begin
    ProjectPath := Trim(ProjectPage.Values[0]);

    if not FileExists(AddBackslash(ProjectPath) + 'compose.yaml') then
    begin
      MsgBox(
        'Arquivo compose.yaml nao encontrado na pasta selecionada.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath: string;
  ConfigDir: string;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigPath := ConfigFilePath;
    ConfigDir := ExtractFileDir(ConfigPath);

    if not DirExists(ConfigDir) then
      ForceDirectories(ConfigDir);

    SetIniString(
      'Desktop',
      'ProjectPath',
      ProjectPage.Values[0],
      ConfigPath
    );
  end;
end;
