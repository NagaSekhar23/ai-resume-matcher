from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from docx import Document

from backend.app.extraction import TextExtractionError, extract_docx_text, extract_pdf_text, extract_txt_text, normalize_extension


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


def test_pdf_extraction() -> None:
    extracted = extract_pdf_text(make_pdf("PDF Resume Text"))
    assert "PDF Resume Text" in extracted


def test_docx_extraction() -> None:
    extracted = extract_docx_text(make_docx("DOCX Resume Text"))
    assert "DOCX Resume Text" in extracted


def test_txt_extraction() -> None:
    assert extract_txt_text("TXT Resume Text".encode("utf-8")) == "TXT Resume Text"


def test_invalid_pdf_raises_parse_error() -> None:
    with pytest.raises(TextExtractionError):
        extract_pdf_text(b"not a pdf")


def test_extension_validation() -> None:
    assert normalize_extension("resume.PDF", None) == ".pdf"
    with pytest.raises(ValueError):
        normalize_extension("resume.png", "image/png")
