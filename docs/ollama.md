# Ollama

Ollama enables optional local recruiter-style analysis. It is not required for deterministic resume ranking.

## Install and verify

1. Install Ollama from `https://ollama.com`.
2. Pull the default model:

```bash
ollama pull mistral:latest
```

3. Start Ollama if it is not already running:

```bash
ollama serve
```

4. Verify:

```bash
curl http://localhost:11434/api/tags
```

The response should list `mistral:latest`.

## Configuration

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:latest
```

## Fallback behavior

If Ollama is unavailable, times out, returns invalid JSON, or the model is missing, deterministic ranking remains available. Only the recruiter-style section becomes unavailable.

## Data sent to Ollama

The backend sends only the information needed for top candidates: job description, structured requirements, deterministic scores, evidence, and selected resume content. Ollama runs locally on your machine.
