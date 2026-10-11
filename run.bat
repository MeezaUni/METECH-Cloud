@echo off
rem METECH Cloud - KMRL Depot Planner. Installs what it needs, builds the dashboard and serves http://127.0.0.1:8010
setlocal
cd /d "%~dp0"
title METECH Cloud - KMRL Depot Planner

rem ---- prerequisites -------------------------------------------------------
where npm >nul 2>nul
if errorlevel 1 (
  echo [!] Node.js 20 or newer is required. Install it from https://nodejs.org/ and run this again.
  pause & exit /b 1
)
where uv >nul 2>nul
if errorlevel 1 (
  echo uv ^(the Python package manager^) is not installed.
  choice /c YN /m "Install uv now from https://astral.sh/uv"
  if errorlevel 2 ( echo Install it from https://docs.astral.sh/uv/ and run this again. & pause & exit /b 1 )
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>nul || ( echo [!] uv is still not available. Open a new terminal and run this again. & pause & exit /b 1 )

rem ---- Gemini key (asked once) ---------------------------------------------
if not exist backend\.env copy backend\.env.example backend\.env >nul
findstr /r /c:"^GEMINI_API_KEY=[A-Za-z0-9]" backend\.env >nul
if errorlevel 1 call :ask_key

rem ---- build and run --------------------------------------------------------
pushd frontend
if not exist node_modules ( call npm ci || ( popd & pause & exit /b 1 ) )
call npm run build || ( popd & pause & exit /b 1 )
popd

pushd backend
uv sync || ( popd & pause & exit /b 1 )
echo.
echo   METECH Cloud is running at http://127.0.0.1:8010   (close this window to stop)
echo.
start "" http://127.0.0.1:8010
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
popd
exit /b

:ask_key
echo.
echo No Gemini API key yet. Get a free one at https://aistudio.google.com/apikey
set "KEY="
set /p "KEY=Paste it here, or press Enter to use the built-in rule engine: "
if not defined KEY exit /b
powershell -NoProfile -Command "$k = $env:KEY.Trim(); (Get-Content backend\.env) -replace '^GEMINI_API_KEY=.*', ('GEMINI_API_KEY=' + $k) | Set-Content -Encoding ascii backend\.env"
echo Saved to backend\.env
exit /b
