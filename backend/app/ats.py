from __future__ import annotations

import re
from dataclasses import dataclass

from .skills import find_skill_mentions
from .text_processing import normalize_text


@dataclass(frozen=True)
class ATSReport:
    score: float
    checks: dict[str, bool]
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"score": round(self.score, 2), "checks": self.checks, "notes": self.notes}


def estimate_ats_score(resume_text: str, keyword_coverage: float = 0.0) -> ATSReport:
    normalized = normalize_text(resume_text)
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]

    checks = {
        "extractable_text": len(normalized.split()) >= 30,
        "contact_information": bool(re.search(r"\b[\w.+-]+@[\w.-]+\.\w+\b", resume_text)) or bool(re.search(r"\b\d{3}[-.)\s]?\d{3}[-.\s]?\d{4}\b", resume_text)),
        "skills_section": any(normalize_text(line).strip(":") in {"skills", "technical skills"} for line in lines),
        "experience_section": any("experience" in normalize_text(line) for line in lines),
        "education_section": any("education" in normalize_text(line) for line in lines),
        "consistent_dates": bool(re.search(r"\b(19|20)\d{2}\b", resume_text)) or bool(re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", normalized)),
        "readable_structure": len(lines) >= 5 and max((len(line) for line in lines), default=0) < 220,
        "keyword_coverage": keyword_coverage >= 0.5,
        "low_unusual_formatting": normalized.count("|") <= 8 and normalized.count("_") <= 5,
        "detected_skills": len(find_skill_mentions(resume_text)) >= 3,
    }

    weights = {
        "extractable_text": 18,
        "contact_information": 12,
        "skills_section": 12,
        "experience_section": 10,
        "education_section": 8,
        "consistent_dates": 8,
        "readable_structure": 10,
        "keyword_coverage": 12,
        "low_unusual_formatting": 5,
        "detected_skills": 5,
    }

    score = sum(weights[name] for name, passed in checks.items() if passed)
    notes = [name.replace("_", " ") for name, passed in checks.items() if not passed]
    return ATSReport(score=min(float(score), 100.0), checks=checks, notes=notes)
