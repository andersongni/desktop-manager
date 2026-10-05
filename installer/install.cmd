@echo off
setlocal
cd /d "%~dp0\.."
echo.
echo === Desktop Manager — Instalacao ===
echo.
python -m src.installer --install
if errorlevel 1 (
  echo.
  echo Falha na instalacao. Verifique se o Python esta no PATH.
  pause
  exit /b 1
)
echo.
pause
