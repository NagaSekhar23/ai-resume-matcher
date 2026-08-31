from __future__ import annotations

import sqlite3

import pytest

from backend.app.database import create_resume_record, delete_resume, get_resume, get_resume_by_hash, list_resumes, update_resume_record


def test_database_crud(isolated_env) -> None:
    created = create_resume_record(
        filename="hash.txt",
        original_filename="resume.txt",
        file_type="txt",
        file_hash="hash",
        extracted_text="Hello database",
    )

    assert created["id"] == 1
    assert get_resume(1)["original_filename"] == "resume.txt"
    assert get_resume_by_hash("hash")["filename"] == "hash.txt"
    assert len(list_resumes()) == 1
    assert delete_resume(1)["file_hash"] == "hash"
    assert get_resume(1) is None


def test_database_update_resume_record(isolated_env) -> None:
    created = create_resume_record(
        filename="hash.txt",
        original_filename="resume.txt",
        file_type="txt",
        file_hash="hash",
        extracted_text="Old text",
    )
    updated = update_resume_record(
        int(created["id"]),
        filename="hash-2.txt",
        original_filename="resume-v2.txt",
        file_type="txt",
        file_hash="hash-2",
        extracted_text="New Python FastAPI text",
    )
    assert updated is not None
    assert updated["original_filename"] == "resume-v2.txt"
    assert get_resume_by_hash("hash-2")["extracted_text"] == "New Python FastAPI text"


def test_duplicate_hash_is_rejected(isolated_env) -> None:
    create_resume_record(
        filename="hash.txt",
        original_filename="first.txt",
        file_type="txt",
        file_hash="same-hash",
        extracted_text="First",
    )
    with pytest.raises(sqlite3.IntegrityError):
        create_resume_record(
            filename="hash-2.txt",
            original_filename="second.txt",
            file_type="txt",
            file_hash="same-hash",
            extracted_text="Second",
        )
