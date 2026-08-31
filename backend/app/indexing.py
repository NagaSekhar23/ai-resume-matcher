from __future__ import annotations

from typing import Dict

from .database import execute_many, execute_write, fetch_all, fetch_one, get_resume, utc_now_iso
from .embeddings import embed_texts, embedding_model_name, serialize_embedding
from .skills import SkillMention, find_skill_mentions
from .text_processing import chunk_resume_text


def _upsert_skill(mention: SkillMention) -> int:
    existing = fetch_one("SELECT id FROM skills WHERE name = ?", (mention.canonical,))
    if existing:
        return int(existing["id"])
    return execute_write(
        "INSERT INTO skills(name, canonical_name, category, created_at) VALUES (?, ?, ?, ?)",
        (mention.canonical, mention.canonical, mention.category, utc_now_iso()),
    )


def index_resume(resume_id: int, force: bool = False) -> Dict[str, object]:
    resume = get_resume(resume_id)
    if resume is None:
        raise ValueError("Resume not found.")

    model_name = embedding_model_name()
    metadata = fetch_one("SELECT * FROM embedding_index_metadata WHERE resume_id = ?", (resume_id,))
    if (
        metadata
        and not force
        and metadata["resume_hash"] == resume["file_hash"]
        and metadata["embedding_model"] == model_name
    ):
        return {
            "resume_id": resume_id,
            "indexed": False,
            "chunk_count": int(metadata["chunk_count"]),
            "embedding_model": model_name,
        }

    chunks = chunk_resume_text(str(resume["extracted_text"]))
    if not chunks:
        chunks = chunk_resume_text(" ".join(str(resume["extracted_text"]).split()))

    vectors = embed_texts([chunk.normalized_text for chunk in chunks])
    timestamp = utc_now_iso()

    execute_write("DELETE FROM resume_chunks WHERE resume_id = ?", (resume_id,))
    execute_write("DELETE FROM resume_skills WHERE resume_id = ?", (resume_id,))

    chunk_values = [
        (
            resume_id,
            chunk.index,
            chunk.section,
            chunk.text,
            chunk.normalized_text,
            serialize_embedding(vector),
            model_name,
            timestamp,
            timestamp,
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    execute_many(
        """
        INSERT INTO resume_chunks(
            resume_id, chunk_index, section, text, normalized_text,
            embedding, embedding_model, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        chunk_values,
    )

    mentions: dict[str, SkillMention] = {}
    for chunk in chunks:
        for mention in find_skill_mentions(chunk.text, chunk.section):
            mentions.setdefault(mention.canonical, mention)

    skill_values = []
    for mention in mentions.values():
        skill_id = _upsert_skill(mention)
        skill_values.append((resume_id, skill_id, mention.evidence, mention.section, 1.0, timestamp))
    if skill_values:
        execute_many(
            """
            INSERT OR REPLACE INTO resume_skills(
                resume_id, skill_id, evidence, section, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            skill_values,
        )

    execute_write("DELETE FROM embedding_index_metadata WHERE resume_id = ?", (resume_id,))
    execute_write(
        """
        INSERT INTO embedding_index_metadata(
            resume_id, resume_hash, embedding_model, chunk_count, indexed_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (resume_id, resume["file_hash"], model_name, len(chunks), timestamp),
    )

    return {
        "resume_id": resume_id,
        "indexed": True,
        "chunk_count": len(chunks),
        "embedding_model": model_name,
        "skills": sorted(mentions.keys()),
    }


def index_all_resumes() -> list[Dict[str, object]]:
    rows = fetch_all("SELECT id FROM resumes ORDER BY id")
    return [index_resume(int(row["id"])) for row in rows]
