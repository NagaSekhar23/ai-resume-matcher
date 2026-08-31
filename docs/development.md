# Development

## Principles

- Preserve local-first behavior.
- Keep scoring evidence-based and deterministic where possible.
- Do not send private resumes to hosted services by default.
- Avoid committing runtime data.
- Add tests for behavior changes.

## Backend

Run tests with sentence-transformers disabled for fast deterministic CI:

```bash
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

## macOS launcher source

The launcher scripts discover the project root from their own location. Generated launchd plists are written under `logs/launchd/` and ignored because they contain local absolute paths.
