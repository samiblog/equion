; Equion Desk 설치 파일 (Inno Setup 6). desk/build/make.py 가 만든다:
;   ISCC /DAppVersion=0.1.0 /DSourceDir=..\dist\EquionDesk equiondesk.iss
; 사용자별 설치(관리자 권한 없음 — DECISIONS D39). 설치 폴더 안의 Python 런타임 하나로 앱·터미널·작업 프로세스가 돈다.
; 실행기는 바로 가기다(D40): runtime\pythonw.exe -I -m equion_desk — 격리 모드라 PC의 Python 설정을 읽지 않는다.
; 틀은 Lectern 0.69.1(cd7fb26)의 installer/lectern.iss 를 따랐다.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\EquionDesk"
#endif

[Setup]
AppId={{6F0C1B7E-3D52-4B0A-9C41-7E5A2D8B94F3}
AppName=Equion Desk
AppVersion={#AppVersion}
AppVerName=Equion Desk {#AppVersion}
AppPublisher=Equion
VersionInfoDescription=Equion Desk Setup
DefaultDirName={autopf}\EquionDesk
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=EquionDesk-{#AppVersion}-setup
UninstallDisplayName=Equion Desk
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto
SetupIconFile=..\equion_desk\assets\equion-desk.ico
UninstallDisplayIcon={app}\equion-desk.ico

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
korean.OpenWith=Equion Desk로 열기
english.OpenWith=Open with Equion Desk
korean.ContextMenuTask=탐색기 폴더 우클릭에 'Equion Desk로 열기' 추가
english.ContextMenuTask=Add 'Open with Equion Desk' to the folder right-click menu in Explorer
korean.DesktopIconTask=바탕화면에 바로가기 만들기
english.DesktopIconTask=Create a desktop shortcut
korean.ExtraTasks=추가 작업:
english.ExtraTasks=Additional tasks:
korean.AppComment=방정식 모형을 만들고 검증하고 전망하는 작업대
english.AppComment=A workbench for building, validating and forecasting with equation models
korean.NoWebView2=이 PC에 Microsoft Edge WebView2 런타임이 없습니다. Equion Desk 창을 띄우려면 필요합니다.%n%n설치는 계속할 수 있습니다. 설치를 마친 뒤 Microsoft 사이트에서 "WebView2 런타임"을 받아 설치하세요.
english.NoWebView2=Microsoft Edge WebView2 Runtime is not installed on this PC. Equion Desk needs it to show its window.%n%nSetup can continue. After it finishes, download "WebView2 Runtime" from the Microsoft website and install it.

[Tasks]
Name: "contextmenu"; Description: "{cm:ContextMenuTask}"; GroupDescription: "{cm:ExtraTasks}"
Name: "desktopicon"; Description: "{cm:DesktopIconTask}"; GroupDescription: "{cm:ExtraTasks}"; Flags: unchecked

[InstallDelete]
; 새 판은 런타임째 바꾼다(제자리 갱신 없음) — 옛 판의 파일이 남아 섞이지 않게
Type: filesandordirs; Name: "{app}\runtime"

[Files]
Source: "{#SourceDir}\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\runtime.json"; DestDir: "{app}"; Flags: ignoreversion
; 바로 가기·우클릭 메뉴·제거 목록의 아이콘 — 실행기가 pythonw.exe 라 따로 준다(창의 아이콘은 앱이 뜨면서 단다)
Source: "..\equion_desk\assets\equion-desk.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; DestName: "THIRD-PARTY-NOTICES-equion.md"; Flags: ignoreversion
Source: "..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Equion Desk"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m equion_desk"; WorkingDir: "{app}"; Comment: "{cm:AppComment}"; AppUserModelID: "Equion.Desk"; IconFilename: "{app}\equion-desk.ico"
Name: "{autodesktop}\Equion Desk"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m equion_desk"; WorkingDir: "{app}"; Comment: "{cm:AppComment}"; AppUserModelID: "Equion.Desk"; IconFilename: "{app}\equion-desk.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\Directory\shell\EquionDesk"; ValueType: string; ValueName: ""; ValueData: "{cm:OpenWith}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\EquionDesk"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\equion-desk.ico"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\EquionDesk\command"; ValueType: string; ValueName: ""; ValueData: """{app}\runtime\pythonw.exe"" -I -m equion_desk ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\EquionDesk"; ValueType: string; ValueName: ""; ValueData: "{cm:OpenWith}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\EquionDesk"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\equion-desk.ico"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\EquionDesk\command"; ValueType: string; ValueName: ""; ValueData: """{app}\runtime\pythonw.exe"" -I -m equion_desk ""%V"""; Tasks: contextmenu

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m equion_desk"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Equion Desk}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 실행하며 생긴 바이트코드(__pycache__)까지 지운다
Type: filesandordirs; Name: "{app}\runtime"

[Code]
const
  WebView2Key = '\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

{ 창은 Microsoft Edge WebView2 런타임으로 그린다. Windows 11 에는 기본으로 있고 Windows 10 도 대부분 있다 }
function WebView2Installed(): Boolean;
begin
  Result := HasVersion(HKLM, 'SOFTWARE\WOW6432Node' + WebView2Key) or HasVersion(HKLM, 'SOFTWARE' + WebView2Key)
    or HasVersion(HKCU, 'Software' + WebView2Key);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not WebView2Installed() then
    SuppressibleMsgBox(CustomMessage('NoWebView2'), mbInformation, MB_OK, IDOK);
end;
