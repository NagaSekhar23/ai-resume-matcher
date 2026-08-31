# Data Storage

Runtime data is local by default and intentionally ignored by Git.

| Path | Purpose | Publish? |
| --- | --- | --- |
| `data/db/resumes.sqlite3` | SQLite database | No |
| `data/uploads/` | Uploaded resume files | No |
| `data/cache/` | Runtime cache files if used | No |
| `data/embeddings/` | Runtime embedding/index artifacts if used | No |
| `logs/` | Local service logs and generated launchd plists | No |

A fresh clone includes only `.gitkeep` placeholders so directories exist without exposing private data.
