from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
from docx import Document
from fastapi.testclient import TestClient

from backend.app.indexing import index_resume


def make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    return document.tobytes()


def make_docx(text: str) -> bytes:
    buffer = BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, filename: str, content: bytes, content_type: str):
    return client.post("/api/resumes", files={"file": (filename, content, content_type)})


def test_resume_upload_api_for_txt(client: TestClient) -> None:
    response = upload(client, "resume.txt", b"Jane Resume TXT", "text/plain")
    assert response.status_code == 201
    payload = response.json()
    assert payload["file_type"] == "txt"
    assert payload["original_filename"] == "resume.txt"
    assert payload["extracted_text"] == "Jane Resume TXT"

    list_response = client.get("/api/resumes")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1


def test_resume_upload_api_for_pdf_and_docx(client: TestClient) -> None:
    pdf_response = upload(client, "resume.pdf", make_pdf("PDF API Text"), "application/pdf")
    docx_response = upload(
        client,
        "resume.docx",
        make_docx("DOCX API Text"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert pdf_response.status_code == 201
    assert docx_response.status_code == 201
    assert "PDF API Text" in pdf_response.json()["extracted_text"]
    assert "DOCX API Text" in docx_response.json()["extracted_text"]


def test_duplicate_detection(client: TestClient) -> None:
    content = b"Duplicate Resume"
    first = upload(client, "resume.txt", content, "text/plain")
    duplicate = upload(client, "resume-copy.txt", content, "text/plain")
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Duplicate resume already uploaded."
    assert client.get("/api/resumes").json()["count"] == 1


def test_invalid_file_handling(client: TestClient) -> None:
    response = upload(client, "resume.png", b"not allowed", "image/png")
    assert response.status_code == 400
    assert "PDF, DOCX, and TXT" in response.json()["detail"]


def test_corrupt_file_handling(client: TestClient) -> None:
    response = upload(client, "resume.pdf", b"not a real pdf", "application/pdf")
    assert response.status_code == 422
    assert "PDF could not be parsed" in response.json()["detail"]


def test_resume_deletion_api(client: TestClient, isolated_env: Path) -> None:
    created = upload(client, "resume.txt", b"Delete Me", "text/plain").json()
    stored_file = isolated_env / "uploads" / created["filename"]
    assert stored_file.exists()

    delete_response = client.delete(f"/api/resumes/{created['id']}")
    assert delete_response.status_code == 204
    assert client.get("/api/resumes").json()["count"] == 0
    assert not stored_file.exists()


def test_resume_replace_api_reindexes_only_replaced_resume(client: TestClient, isolated_env: Path) -> None:
    first = upload(client, "backend.txt", b"Python FastAPI PostgreSQL", "text/plain").json()
    second = upload(client, "frontend.txt", b"React TypeScript", "text/plain").json()

    first_reuse = client.post(f"/api/resumes/{first['id']}/index").json()
    second_reuse = client.post(f"/api/resumes/{second['id']}/index").json()
    assert first_reuse["indexed"] is True
    assert second_reuse["indexed"] is True

    replacement = client.put(
        f"/api/resumes/{first['id']}",
        files={"file": ("backend-v2.txt", b"Python FastAPI PostgreSQL Kubernetes", "text/plain")},
    )
    assert replacement.status_code == 200
    assert replacement.json()["original_filename"] == "backend-v2.txt"

    unchanged = index_resume(int(second["id"]))
    replaced = index_resume(int(first["id"]))
    assert unchanged["indexed"] is False
    assert replaced["indexed"] is False
    assert (isolated_env / "uploads" / replacement.json()["filename"]).exists()


def test_missing_resume_returns_404(client: TestClient) -> None:
    assert client.get("/api/resumes/999").status_code == 404
    assert client.delete("/api/resumes/999").status_code == 404
