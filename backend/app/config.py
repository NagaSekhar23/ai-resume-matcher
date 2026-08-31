from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.database_path = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "db" / "resumes.sqlite3"))
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
            if origin.strip()
        ]
        self.max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
        self.use_sentence_transformers = os.getenv("USE_SENTENCE_TRANSFORMERS", "0").strip().lower() not in {"0", "false", "no"}


def get_settings() -> Settings:
    return Settings()
