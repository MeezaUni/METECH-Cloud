@echo off
rem KMRL Depot Planner - cloud AI edition. Builds the UI and serves everything on http://127.0.0.1:8010
setlocal
cd /d "%~dp0"
where uv >nul 2>nul || (echo [!] uv is required: https://docs.astral.sh/uv/getting-started/installation/ & exit /b 1)
where npm >nul 2>nul || (echo [!] Node.js is required: https://nodejs.org/ & exit /b 1)

pushd frontend
if not exist node_modules call npm install || exit /b 1
call npm run build || exit /b 1
popd

pushd backend
if not exist .env copy .env.example .env >nul
uv sync || exit /b 1
echo.
echo   KMRL Depot Planner (cloud AI) on http://127.0.0.1:8010
echo   Put your Gemini key in backend\.env to enable the AI; without it the rule engine is used.
echo.
start "" http://127.0.0.1:8010
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
