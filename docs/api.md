# API

Base URL: `http://127.0.0.1:8000`.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Health check. |
| `POST` | `/api/resumes` | Upload PDF, DOCX, or TXT resume. |
| `GET` | `/api/resumes` | List stored resumes. |
| `GET` | `/api/resumes/{id}` | Get one resume. |
| `PUT` | `/api/resumes/{id}` | Replace one resume and invalidate/rebuild relevant index data. |
| `DELETE` | `/api/resumes/{id}` | Delete resume metadata and uploaded file. |
| `POST` | `/api/resumes/{id}/index` | Index/re-index a resume. |
| `POST` | `/api/jobs/analyze` | Analyze all stored resumes against a job description. |
| `GET` | `/api/analyses/{id}` | Retrieve a previous analysis. |
| `POST` | `/api/analyses/{id}/recruiter` | Run optional local Ollama recruiter analysis. |
| `POST` | `/api/analyses/{id}/compare` | Compare selected resumes in an analysis. |
| `GET` | `/api/history` | List analysis history. |
| `DELETE` | `/api/history/{id}` | Delete analysis history. |
| `GET` | `/api/settings` | Read app settings. |
| `PUT` | `/api/settings` | Update app settings. |
| `GET` | `/api/llm/status` | Check Ollama/provider availability. |

Interactive OpenAPI docs are available at `/docs` when the backend is running.
