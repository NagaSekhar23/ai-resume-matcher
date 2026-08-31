# Privacy

AI Resume Matcher is designed for local-first use.

## Stored locally

- Uploaded resume files
- Extracted resume text
- SQLite database records
- Skills, chunks, embeddings/index metadata
- Job descriptions and analysis history
- Local settings and logs

## External services

No OpenAI, Anthropic, Gemini, or paid AI API is required. The optional recruiter analysis uses Ollama at `localhost` by default.

## What can leave your machine?

The application code does not intentionally send resumes to a cloud AI provider. If you change configuration to point Ollama or APIs at a remote server, that is outside the default local-first setup.

## Publishing safety

Do not commit files under `data/`, `logs/`, `.env`, `.venv`, `frontend/.next`, or `frontend/node_modules`.
