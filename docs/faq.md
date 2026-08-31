# FAQ

## Does the app require paid AI APIs?

No. Core matching is local. Ollama is optional for local recruiter-style analysis.

## Are ATS scores official?

No. ATS compatibility is a heuristic estimate based on measurable checks such as extractable text, section headings, contact info, and keyword coverage.

## Can I use scanned PDFs?

Scanned PDFs may extract little or no text because OCR is not included.

## Where is my data?

By default, in `data/db/` and `data/uploads/` inside your local project folder.

## Can I publish my fork safely?

Check `git status --ignored` and confirm `data/`, `logs/`, `.env`, `.venv`, `.next`, and `node_modules` are not staged.
