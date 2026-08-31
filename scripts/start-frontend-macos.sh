#!/bin/zsh
set -u
setopt null_glob

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_URL="http://127.0.0.1:8000"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
if ! command -v npm >/dev/null 2>&1; then
  for candidate in "$HOME"/.nvm/versions/node/*/bin/npm; do
    export PATH="$(dirname "$candidate"):$PATH"
    break
  done
fi
export NEXT_PUBLIC_API_BASE_URL="$BACKEND_URL"

cd "$FRONTEND_DIR" || exit 1

NPM_BIN="$(command -v npm || true)"
if [[ -z "$NPM_BIN" ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: npm was not found for launchd. Install Node.js or ensure npm is available in a standard Homebrew, system, or NVM location."
  exit 127
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Using npm at $NPM_BIN"

if [[ ! -f "$FRONTEND_DIR/.next/BUILD_ID" ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Production build missing; running npm run build before starting frontend."
  "$NPM_BIN" run build || exit 1
fi

exec "$NPM_BIN" run start -- --hostname 127.0.0.1 --port 3000
