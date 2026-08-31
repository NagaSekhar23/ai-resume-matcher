from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    database_path = tmp_path / "db" / "resumes.sqlite3"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("USE_SENTENCE_TRANSFORMERS", "0")
    return tmp_path


@pytest.fixture()
def client(isolated_env: Path) -> TestClient:
    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client
