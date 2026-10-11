#!/usr/bin/env bash
# METECH Cloud - KMRL Depot Planner. Installs what it needs, builds the dashboard and serves http://127.0.0.1:8010
set -euo pipefail
cd "$(dirname "$0")"

command -v npm >/dev/null || { echo "Node.js 20 or newer is required: https://nodejs.org/"; exit 1; }
if ! command -v uv >/dev/null; then
  read -r -p "uv (the Python package manager) is not installed. Install it now from https://astral.sh/uv? [y/N] " ok
  [[ "$ok" =~ ^[Yy] ]] || { echo "Install it from https://docs.astral.sh/uv/ and run this again."; exit 1; }
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

[ -f backend/.env ] || cp backend/.env.example backend/.env
if ! grep -qE '^GEMINI_API_KEY=[A-Za-z0-9]' backend/.env; then
  echo "No Gemini API key yet. Get a free one at https://aistudio.google.com/apikey"
  read -r -p "Paste it here, or press Enter to use the built-in rule engine: " key
  if [ -n "$key" ]; then
    tmp=$(mktemp); sed "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${key}|" backend/.env > "$tmp" && mv "$tmp" backend/.env
    echo "Saved to backend/.env"
  fi
fi

(cd frontend && { [ -d node_modules ] || npm ci; } && npm run build)
cd backend
uv sync --inexact
echo; echo "  METECH Cloud is running at http://127.0.0.1:8010   (Ctrl+C to stop)"; echo
[ -n "${KMRL_NO_BROWSER:-}" ] || ( sleep 3; (command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:8010) || (command -v open >/dev/null && open http://127.0.0.1:8010) || true ) &
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
