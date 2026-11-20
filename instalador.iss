; Script do Inno Setup 6 (gratuito: https://jrsoftware.org/isdl.php).
; Não precisa abrir este arquivo: o criar-instalador.bat usa ele sozinho.
#define NomeApp "Retro Boom Box"
#ifndef Versao
#define Versao "0.4.1"
#endif

[Setup]
AppId={{B3C2F8A1-5D4E-4F7A-9C61-2E8A7D1B0F43}
AppName={#NomeApp}
AppVersion={#Versao}
AppPublisher=Retro Boom Box
DefaultDirName={autopf}\Retro Boom Box
DefaultGroupName=Retro Boom Box
DisableProgramGroupPage=yes
OutputDir=instalador
OutputBaseFilename=RetroBoomBox-Instalador-{#Versao}
SetupIconFile=app\assets\icone.ico
UninstallDisplayIcon={app}\RetroBoomBox.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos:"
Name: "abrircom"; Description: "Mostrar o Retro Boom Box na lista “Abrir com” de músicas e vídeos"; GroupDescription: "Arquivos:"

[Files]
Source: "dist\RetroBoomBox\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "exemplos\*"; DestDir: "{app}\exemplos"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "GUIA-DE-SKINS.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LEIAME.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Retro Boom Box"; Filename: "{app}\RetroBoomBox.exe"
Name: "{autoprograms}\Retro Boom Box - Guia de skins"; Filename: "{app}\GUIA-DE-SKINS.txt"
Name: "{autodesktop}\Retro Boom Box"; Filename: "{app}\RetroBoomBox.exe"; Tasks: atalho

[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Retro Boom Box"; Flags: uninsdeletekey; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\shell\open\command"; ValueType: string; ValueData: """{app}\RetroBoomBox.exe"" ""%1"""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mp3"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".flac"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".wav"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".ogg"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".oga"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".opus"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".m4a"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".aac"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".wma"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".aiff"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".aif"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mka"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".avi"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mov"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".wmv"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".m4v"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mpg"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".mpeg"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".flv"; ValueData: ""; Tasks: abrircom
Root: HKA; Subkey: "Software\Classes\Applications\RetroBoomBox.exe\SupportedTypes"; ValueType: string; ValueName: ".3gp"; ValueData: ""; Tasks: abrircom

[Run]
Filename: "{app}\RetroBoomBox.exe"; Description: "Abrir o Retro Boom Box agora"; Flags: nowait postinstall skipifsilent

; Observação: desinstalar remove o programa, mas NÃO apaga a sua biblioteca, playlists, skins e
; configurações (ficam em %APPDATA%\RetroBoomBox). Para apagar tudo, apague essa pasta.
