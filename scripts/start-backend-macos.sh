#!/bin/zsh
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_URL="http://127.0.0.1:8000"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export DATABASE_PATH="$ROOT_DIR/data/db/resumes.sqlite3"
export UPLOAD_DIR="$ROOT_DIR/data/uploads"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="mistral:latest"
export USE_SENTENCE_TRANSFORMERS="${USE_SENTENCE_TRANSFORMERS:-0}"

cd "$ROOT_DIR" || exit 1
exec "$ROOT_DIR/.venv/bin/python" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
