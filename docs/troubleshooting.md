# Troubleshooting

## Frontend connection refused

Start the frontend:

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Then check `http://127.0.0.1:3000/`.

## Backend unavailable

Start the backend:

```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/api/health`.

## Ollama unavailable

Run:

```bash
ollama serve
ollama pull mistral:latest
curl http://localhost:11434/api/tags
```

The app still performs deterministic matching without Ollama.

## macOS launcher cannot find npm

If you use NVM, GUI launch contexts may not inherit your shell PATH. `scripts/start-frontend-macos.sh` searches common Homebrew and NVM locations. Install Node in a standard location or update your local launcher script.
