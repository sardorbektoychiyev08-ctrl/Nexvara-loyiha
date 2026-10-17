; NEXVARA Personal installer (Inno Setup 6). Built by scripts\build.ps1:
;   ISCC /DAppVersion=0.1.0 /DSourceDir=..\dist\NEXVARA installer\nexvara.iss
; Per-user install (no admin rights), Start Menu + optional desktop icon, uninstaller.
; User data in D:\NEXVARA (settings, app.db, textbooks, keys in Credential Manager) is
; never installed, changed or removed here, so upgrades and uninstalls keep it.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\NEXVARA"
#endif

[Setup]
AppId={{6F4B2A31-9C1E-4E59-A1D7-5B3C0E8F7A21}
AppName=NEXVARA Personal
AppVersion={#AppVersion}
AppVerName=NEXVARA Personal {#AppVersion}
AppPublisher=NEXVARA
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\NEXVARA
DefaultGroupName=NEXVARA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=NEXVARA-Setup-{#AppVersion}
SetupIconFile=..\build\nexvara.ico
UninstallDisplayIcon={app}\NEXVARA.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Ish stolida yorliq"; GroupDescription: "Yorliqlar:"

[InstallDelete]
; Old program files are replaced as a whole (a stale module must not survive an upgrade).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NEXVARA"; Filename: "{app}\NEXVARA.exe"
Name: "{group}\NEXVARA o'chirish"; Filename: "{uninstallexe}"
Name: "{userdesktop}\NEXVARA"; Filename: "{app}\NEXVARA.exe"; Tasks: desktopicon

[Run]
; Also after a silent update (the updater closes the app and expects it back).
Filename: "{app}\NEXVARA.exe"; Description: "NEXVARA'ni ishga tushirish"; Flags: nowait postinstall; Check: not CmdLineParamExists('/NOLAUNCH')

[Code]
function CmdLineParamExists(const Value: string): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;
