@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Criar o instalador do Retro Boom Box
set "PY=python"
where py >nul 2>nul && set "PY=py"

echo ============================================================
echo  Criando o Retro Boom Box.exe e o instalador
echo  (na primeira vez baixa o que precisa e demora uns minutos)
echo ============================================================
echo.
echo [1/4] Preparando o ambiente de montagem...
if not exist ".venv-build\Scripts\python.exe" (
  %PY% -m venv .venv-build || goto erro
)
".venv-build\Scripts\python.exe" -m pip install --upgrade pip || goto erro
".venv-build\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller || goto erro

echo.
echo [2/4] Montando o programa (isso demora alguns minutos)...
".venv-build\Scripts\python.exe" -m PyInstaller RetroBoomBox.spec --noconfirm --clean || goto erro

echo.
echo [3/4] Testando o programa montado...
if exist autoteste.txt del autoteste.txt
start /wait "" "dist\RetroBoomBox\RetroBoomBox.exe" --autoteste
if errorlevel 1 goto erro_teste
type autoteste.txt

echo.
echo [4/4] Criando o instalador...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if not defined ISCC goto sem_inno
rem O numero da versao vem do arquivo app\__init__.py (assim ele fica escrito num lugar so).
set "VERSAO="
for /f "tokens=2 delims== " %%V in ('findstr /b "__version__" "app\__init__.py"') do set "VERSAO=%%~V"
set "OPCAO_VERSAO="
if defined VERSAO set "OPCAO_VERSAO=/DVersao=%VERSAO%"
echo Versao: %VERSAO%
"%ISCC%" %OPCAO_VERSAO% instalador.iss || goto erro
echo.
echo ============================================================
echo  PRONTO! O instalador esta na pasta "instalador".
echo ============================================================
explorer instalador
pause
exit /b 0

:sem_inno
echo.
echo ============================================================
echo  O programa foi montado na pasta "dist\RetroBoomBox".
echo  Ele ja funciona sem instalar: abra RetroBoomBox.exe de la.
echo.
echo  Para gerar tambem o INSTALADOR (um unico arquivo Setup.exe):
echo   1. Instale o Inno Setup 6 (gratis): https://jrsoftware.org/isdl.php
echo   2. Rode este arquivo criar-instalador.bat de novo.
echo ============================================================
explorer "dist\RetroBoomBox"
pause
exit /b 0

:erro_teste
echo.
echo O programa montado nao passou no teste. Veja o arquivo autoteste.txt
echo (se ele existir) e me envie o conteudo.
pause
exit /b 1

:erro
echo.
echo Algo deu errado na montagem. Confira se o Python 3.10 a 3.13 esta instalado
echo (site python.org, com "Add Python to PATH" marcado), se ha internet e tente de novo.
echo Se continuar, me envie as ultimas linhas desta janela.
pause
exit /b 1
