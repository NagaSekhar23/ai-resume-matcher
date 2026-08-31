# Testing

## Backend

The backend test suite covers extraction, upload validation, duplicate detection, database CRUD, matching, indexing, caching, settings, comparison, history, and LLM fallback behavior.

```bash
source .venv/bin/activate
USE_SENTENCE_TRANSFORMERS=0 python -m pytest -q
```

## Frontend

```bash
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

## Ollama

Normal CI does not require Ollama. LLM-dependent behavior should be tested with mocks or local manual verification.
