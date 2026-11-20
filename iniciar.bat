@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Retro Boom Box
set "PY=python"
where py >nul 2>nul && set "PY=py"

if not exist ".venv\Scripts\python.exe" (
  echo Preparando o Retro Boom Box pela primeira vez. Isso pode levar alguns minutos...
  %PY% -m venv .venv || goto erro
  ".venv\Scripts\python.exe" -m pip install --upgrade pip || goto erro
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto erro
)

".venv\Scripts\python.exe" -m app.main %*
if errorlevel 1 pause
exit /b 0

:erro
echo.
echo Algo deu errado na instalacao.
echo Confira se o Python 3.10 a 3.13 esta instalado (site python.org) e se a opcao
echo "Add Python to PATH" foi marcada na instalacao. Depois tente de novo.
pause
exit /b 1
