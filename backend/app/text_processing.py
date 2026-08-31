from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


SECTION_HEADINGS = {
    "summary",
    "profile",
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "projects",
    "skills",
    "technical skills",
    "education",
    "certifications",
}


@dataclass(frozen=True)
class TextChunk:
    index: int
    section: str
    text: str
    normalized_text: str


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("–", "-").replace("—", "-")
    lowered = re.sub(r"[^a-z0-9+#./\-\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def split_sentences(text: str) -> List[str]:
    stripped = text.strip()
    if not stripped:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", stripped)
    return [part.strip(" -•\\t") for part in parts if part.strip(" -•\\t")]


def detect_section(line: str) -> str:
    normalized = normalize_text(line).strip(":")
    if normalized in SECTION_HEADINGS:
        return normalized
    return ""


def chunk_resume_text(text: str, max_chars: int = 900) -> List[TextChunk]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    current_section = "general"
    section_sentences: list[tuple[str, str]] = []

    if not lines:
        return []

    for line in lines:
        section = detect_section(line)
        if section and len(line) <= 40:
            current_section = section
            continue
        for sentence in split_sentences(line):
            section_sentences.append((current_section, sentence))

    if not section_sentences:
        section_sentences = [("general", text.strip())]

    chunks: list[TextChunk] = []
    buffer: list[str] = []
    buffer_section = section_sentences[0][0]

    def flush() -> None:
        if not buffer:
            return
        chunk_text = " ".join(buffer).strip()
        chunks.append(
            TextChunk(
                index=len(chunks),
                section=buffer_section,
                text=chunk_text,
                normalized_text=normalize_text(chunk_text),
            )
        )
        buffer.clear()

    for section, sentence in section_sentences:
        proposed = " ".join(buffer + [sentence])
        if buffer and (section != buffer_section or len(proposed) > max_chars):
            flush()
            buffer_section = section
        if not buffer:
            buffer_section = section
        buffer.append(sentence)
    flush()

    return chunks


def contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms)
