@echo off
REM FieldRook desktop launcher bootstrap (M025 BETA).
REM Runs the PowerShell launcher with a process-scoped execution policy
REM bypass (no machine setting is changed). All arguments pass through:
REM   FieldRook.bat [-Port 8000] [-NoBrowser] [-Stop] [-CheckOnly]
setlocal
set "HERE=%~dp0"
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo [FieldRook] powershell.exe was not found. FieldRook Desktop requires Windows PowerShell.
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%HERE%FieldRook-Launcher.ps1" %*
exit /b %ERRORLEVEL%
