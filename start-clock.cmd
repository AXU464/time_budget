@echo off
setlocal
rem Resolve Python from PATH; the project can be placed in any directory.
where.exe pyw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pyw.exe -3 "%~dp0clock.pyw"
    exit /b 0
)
where.exe pythonw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pythonw.exe "%~dp0clock.pyw"
    exit /b 0
)
echo Python 3 was not found. Install Python with tkinter and enable its launcher or add Python to PATH.
pause
exit /b 1
