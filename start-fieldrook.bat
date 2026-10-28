@echo off
REM FieldRook one-command starter (M024). Opens two windows: backend :8000, frontend :5173.
REM Localhost only. Ctrl+C in each window stops it. See docs\FIRST_RUN.md for the explicit path.
setlocal

cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo [FieldRook] backend venv missing. Run first:
  echo   cd backend ^&^& python -m venv .venv ^&^& .\.venv\Scripts\python -m pip install -r requirements.txt
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [FieldRook] frontend dependencies missing. Run first:
  echo   cd frontend ^&^& pnpm install
  exit /b 1
)

echo [FieldRook] starting backend on http://127.0.0.1:8000 ...
start "FieldRook backend" /D "%~dp0backend" "%~dp0backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo [FieldRook] starting frontend on http://localhost:5173 ...
start "FieldRook frontend" /D "%~dp0frontend" cmd /c pnpm run dev
echo [FieldRook] both windows launched. Stop each with Ctrl+C.
