# Getting Started

Use this guide to run AI Resume Matcher from a clean clone.

## 1. Clone

```bash
git clone git@github.com:NagaSekhar23/ai-resume-matcher.git
cd ai-resume-matcher
```

## 2. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3. Frontend

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000/`.

## 4. Optional Ollama

Install Ollama, then run `ollama pull mistral:latest`. The app still ranks resumes without Ollama.
