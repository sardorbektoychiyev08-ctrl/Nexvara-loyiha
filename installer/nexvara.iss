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
; Inno Setup has no Uzbek file: the English base with every visible text in Uzbek below.
Name: "uzbek"; MessagesFile: "compiler:Default.isl"

[Messages]
SetupAppTitle=O‘rnatish
SetupWindowTitle=O‘rnatish — %1
UninstallAppTitle=O‘chirish
UninstallAppFullTitle=%1 — o‘chirish
ConfirmTitle=Tasdiqlash
SetupLdrStartupMessage=%1 o‘rnatiladi. Davom etasizmi?
ExitSetupTitle=O‘rnatishdan chiqish
ExitSetupMessage=O‘rnatish tugamadi. Hozir chiqsangiz, dastur o‘rnatilmaydi.%n%nKeyinroq qayta ishga tushirishingiz mumkin.%n%nChiqilsinmi?
ButtonBack=< &Orqaga
ButtonNext=&Keyingi >
ButtonInstall=&O‘rnatish
ButtonOK=OK
ButtonCancel=Bekor qilish
ButtonYes=&Ha
ButtonNo=&Yo‘q
ButtonFinish=&Tayyor
ButtonBrowse=&Tanlash...
BrowseDialogTitle=Papkani tanlash
BrowseDialogLabel=Ro‘yxatdan papkani tanlang va OK ni bosing.
NewFolderName=Yangi papka
WelcomeLabel1=[name] o‘rnatish ustasiga xush kelibsiz
WelcomeLabel2=Kompyuteringizga [name/ver] o‘rnatiladi.%n%nEski versiya bo‘lsa, u yangilanadi. Ma’lumotlaringiz (darsliklar, sozlamalar, Google va AI ulanishlari) saqlanadi.
WizardSelectDir=O‘rnatish joyi
SelectDirDesc=[name] qayerga o‘rnatilsin?
SelectDirLabel3=[name] quyidagi papkaga o‘rnatiladi.
SelectDirBrowseLabel=Davom etish uchun «Keyingi» ni bosing. Boshqa papka uchun «Tanlash» ni bosing.
DiskSpaceGBLabel=Kamida [gb] GB bo‘sh joy kerak.
DiskSpaceMBLabel=Kamida [mb] MB bo‘sh joy kerak.
DirExistsTitle=Papka mavjud
DirExists=Papka:%n%n%1%n%nallaqachon bor. Baribir shu papkaga o‘rnatilsinmi?
WizardSelectTasks=Qo‘shimcha amallar
SelectTasksDesc=Qaysi qo‘shimcha amallar bajarilsin?
SelectTasksLabel2=[name] o‘rnatilayotganda bajariladigan amallarni tanlang va «Keyingi» ni bosing.
WizardReady=O‘rnatishga tayyor
ReadyLabel1=[name] kompyuteringizga o‘rnatishga tayyor.
ReadyLabel2a=Davom etish uchun «O‘rnatish» ni, sozlamalarni ko‘rish uchun «Orqaga» ni bosing.
ReadyLabel2b=Davom etish uchun «O‘rnatish» ni bosing.
ReadyMemoDir=O‘rnatish joyi:
ReadyMemoTasks=Qo‘shimcha amallar:
WizardPreparing=O‘rnatishga tayyorlanmoqda
PreparingDesc=[name] o‘rnatishga tayyorlanmoqda.
ApplicationsFound=Quyidagi dasturlar yangilanadigan fayllardan foydalanmoqda. Ularni avtomatik yopishga ruxsat bering.
ApplicationsFound2=Quyidagi dasturlar yangilanadigan fayllardan foydalanmoqda. Ularni avtomatik yopishga ruxsat bering. O‘rnatish tugagach, ular qayta ochiladi.
CloseApplications=&Dasturlarni avtomatik yopish
DontCloseApplications=&Dasturlarni yopmaslik
WizardInstalling=O‘rnatilmoqda
InstallingLabel=[name] o‘rnatilmoqda, kuting.
FinishedHeadingLabel=[name] o‘rnatildi
FinishedLabelNoIcons=[name] kompyuteringizga o‘rnatildi.
FinishedLabel=[name] kompyuteringizga o‘rnatildi. Uni Start menyusidagi yoki ish stolidagi NEXVARA yorlig‘i orqali ochishingiz mumkin.
ClickFinish=Chiqish uchun «Tayyor» ni bosing.
StatusClosingApplications=Dasturlar yopilmoqda...
StatusCreateDirs=Papkalar yaratilmoqda...
StatusExtractFiles=Fayllar o‘rnatilmoqda...
StatusCreateIcons=Yorliqlar yaratilmoqda...
StatusSavingUninstall=O‘chirish ma’lumotlari saqlanmoqda...
StatusRunProgram=O‘rnatish yakunlanmoqda...
StatusRestartingApplications=Dasturlar qayta ochilmoqda...
StatusRollback=O‘zgarishlar bekor qilinmoqda...
ConfirmUninstall=%1 dasturi kompyuterdan o‘chirilsinmi?%n%nMa’lumotlaringiz (darsliklar, sozlamalar, testlar, Google va AI ulanishlari) o‘chirilmaydi.
UninstallStatusLabel=%1 o‘chirilmoqda, kuting.
UninstalledAll=%1 kompyuterdan o‘chirildi. Ma’lumotlaringiz joyida qoldi.
WizardUninstalling=O‘chirish holati
AdditionalIcons=Qo‘shimcha yorliqlar:
CreateDesktopIcon=Ish stolida &yorliq yaratish

[Tasks]
Name: "desktopicon"; Description: "Ish stolida yorliq"; GroupDescription: "Yorliqlar:"

[InstallDelete]
; Old program files are replaced as a whole (a stale module must not survive an upgrade).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; A copy of this installer, so the updater can roll back to this version later.
Source: "{srcexe}"; DestDir: "{localappdata}\NEXVARA\installers\{#AppVersion}"; DestName: "NEXVARA-Setup-{#AppVersion}.exe"; Flags: external ignoreversion

[Icons]
Name: "{group}\NEXVARA"; Filename: "{app}\NEXVARA.exe"
Name: "{group}\NEXVARA’ni o‘chirish"; Filename: "{uninstallexe}"
Name: "{userdesktop}\NEXVARA"; Filename: "{app}\NEXVARA.exe"; Tasks: desktopicon

[Run]
; Also after a silent update (the updater closes the app and expects it back).
Filename: "{app}\NEXVARA.exe"; Description: "NEXVARA’ni ishga tushirish"; Flags: nowait postinstall; Check: not CmdLineParamExists('/NOLAUNCH')

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
