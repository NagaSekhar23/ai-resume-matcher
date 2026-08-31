# Configuration

Configuration is local and file-based.

## Backend `.env`

| Variable | Description |
| --- | --- |
| `DATABASE_PATH` | SQLite database path. Defaults to `./data/db/resumes.sqlite3`. |
| `UPLOAD_DIR` | Uploaded resume file directory. Defaults to `./data/uploads`. |
| `CORS_ORIGINS` | Comma-separated local frontend origins. |
| `MAX_UPLOAD_BYTES` | Maximum upload size in bytes. |
| `USE_SENTENCE_TRANSFORMERS` | Set to `1` to use sentence-transformers when available locally. |
| `OLLAMA_BASE_URL` | Local Ollama endpoint. Default `http://localhost:11434`. |
| `OLLAMA_MODEL` | Ollama model name. Default `mistral:latest`. |

## Frontend `.env.local`

`NEXT_PUBLIC_API_BASE_URL` points the frontend at the local backend. Default: `http://localhost:8000`.

## Matching weights

Weights are stored in local settings and must total 100. The UI validates this before saving.
