from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    extracted_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_resumes_created_at ON resumes(created_at DESC);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resume_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    evidence TEXT NOT NULL,
    section TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    UNIQUE(resume_id, skill_id),
    FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
    FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    section TEXT NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    embedding BLOB,
    embedding_model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(resume_id, chunk_index),
    FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS embedding_index_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL UNIQUE,
    resume_hash TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    indexed_at TEXT NOT NULL,
    FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_descriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT NOT NULL,
    description_hash TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_description_id INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    resume_count INTEGER NOT NULL,
    cached_result_count INTEGER NOT NULL,
    recruiter_result_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_description_id) REFERENCES job_descriptions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER,
    job_description_id INTEGER NOT NULL,
    resume_id INTEGER NOT NULL,
    cache_key TEXT NOT NULL UNIQUE,
    overall_score REAL NOT NULL,
    ats_score REAL NOT NULL,
    required_skill_score REAL NOT NULL,
    preferred_skill_score REAL NOT NULL,
    semantic_score REAL NOT NULL,
    experience_score REAL NOT NULL,
    responsibilities_score REAL NOT NULL,
    education_score REAL NOT NULL,
    recruiter_fit_score REAL NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id) ON DELETE SET NULL,
    FOREIGN KEY(job_description_id) REFERENCES job_descriptions(id) ON DELETE CASCADE,
    FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_run_score ON analysis_results(analysis_run_id, overall_score DESC);

CREATE TABLE IF NOT EXISTS requirement_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_result_id INTEGER NOT NULL,
    requirement TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence TEXT,
    score REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(analysis_result_id) REFERENCES analysis_results(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS resume_fts USING fts5(
    original_filename,
    extracted_text,
    content='resumes',
    content_rowid='id'
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_database_path() -> Path:
    return get_settings().database_path


def init_db() -> None:
    path = get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        _ensure_column(connection, "analysis_runs", "recruiter_result_json", "TEXT")
        connection.commit()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    init_db()
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def row_to_dict(row: sqlite3.Row) -> Dict[str, object]:
    return dict(row)


def create_resume_record(
    *,
    filename: str,
    original_filename: str,
    file_type: str,
    file_hash: str,
    extracted_text: str,
) -> Dict[str, object]:
    timestamp = utc_now_iso()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO resumes (
                filename, original_filename, file_type, file_hash,
                extracted_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, original_filename, file_type, file_hash, extracted_text, timestamp, timestamp),
        )
        row = connection.execute("SELECT * FROM resumes WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_to_dict(row)


def list_resumes() -> List[Dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM resumes ORDER BY created_at DESC, id DESC").fetchall()
        return [row_to_dict(row) for row in rows]


def get_resume(resume_id: int) -> Optional[Dict[str, object]]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        return row_to_dict(row) if row else None


def get_resume_by_hash(file_hash: str) -> Optional[Dict[str, object]]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM resumes WHERE file_hash = ?", (file_hash,)).fetchone()
        return row_to_dict(row) if row else None


def update_resume_record(
    resume_id: int,
    *,
    filename: str,
    original_filename: str,
    file_type: str,
    file_hash: str,
    extracted_text: str,
) -> Optional[Dict[str, object]]:
    timestamp = utc_now_iso()
    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        if existing is None:
            return None
        connection.execute(
            """
            UPDATE resumes
            SET filename = ?, original_filename = ?, file_type = ?, file_hash = ?,
                extracted_text = ?, updated_at = ?
            WHERE id = ?
            """,
            (filename, original_filename, file_type, file_hash, extracted_text, timestamp, resume_id),
        )
        row = connection.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        return row_to_dict(row)


def delete_resume(resume_id: int) -> Optional[Dict[str, object]]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        if row is None:
            return None
        try:
            connection.execute("DELETE FROM resume_fts WHERE rowid = ?", (resume_id,))
        except sqlite3.DatabaseError:
            pass
        connection.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        return row_to_dict(row)


def upsert_resume_fts(resume_id: int, original_filename: str, extracted_text: str) -> None:
    with get_connection() as connection:
        try:
            connection.execute("DELETE FROM resume_fts WHERE rowid = ?", (resume_id,))
        except sqlite3.DatabaseError:
            pass
        connection.execute(
            "INSERT INTO resume_fts(rowid, original_filename, extracted_text) VALUES (?, ?, ?)",
            (resume_id, original_filename, extracted_text),
        )


def execute_write(query: str, params: tuple[Any, ...] = ()) -> int:
    with get_connection() as connection:
        cursor = connection.execute(query, params)
        return int(cursor.lastrowid)


def execute_many(query: str, values: list[tuple[Any, ...]]) -> None:
    with get_connection() as connection:
        connection.executemany(query, values)


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> Optional[Dict[str, object]]:
    with get_connection() as connection:
        row = connection.execute(query, params).fetchone()
        return row_to_dict(row) if row else None


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> List[Dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [row_to_dict(row) for row in rows]
