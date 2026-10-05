@echo off
setlocal
cd /d "%~dp0\.."
echo.
echo === Desktop Manager — Desinstalacao ===
echo.
python -m src.installer --uninstall
pause
