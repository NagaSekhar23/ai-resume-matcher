from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .ats import estimate_ats_score
from .database import execute_many, execute_write, fetch_all, fetch_one, get_resume, list_resumes, utc_now_iso
from .embeddings import cosine_similarity, deserialize_embedding, embed_texts
from .indexing import index_resume
from .skills import ParsedJobDescription, aliases_for_skill, parse_job_description, related_skills
from .text_processing import normalize_text, split_sentences


MATCH_WEIGHTS = {
    "required_skills": 0.35,
    "preferred_skills": 0.20,
    "semantic_similarity": 0.15,
    "experience_match": 0.10,
    "responsibilities": 0.10,
    "education": 0.05,
    "ats_compatibility": 0.05,
}


@dataclass(frozen=True)
class RequirementMatch:
    requirement: str
    category: str
    status: str
    evidence: Optional[str]
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "requirement": self.requirement,
            "category": self.category,
            "status": self.status,
            "evidence": self.evidence,
            "score": round(self.score, 2),
        }


def stable_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def matching_config_hash(weights: Optional[dict[str, float]] = None) -> str:
    return stable_hash(weights or MATCH_WEIGHTS)


def _score_ratio(matches: list[RequirementMatch]) -> float:
    if not matches:
        return 100.0
    return sum(match.score for match in matches) / len(matches)


def _sentence_evidence(text: str, requirement: str) -> Optional[str]:
    normalized_requirement = normalize_text(requirement)
    aliases = {normalize_text(alias) for alias in aliases_for_skill(normalized_requirement)}
    for sentence in split_sentences(text):
        normalized_sentence = normalize_text(sentence)
        if any(alias and re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized_sentence) for alias in aliases):
            return sentence
    return None


def _partial_evidence(text: str, requirement: str) -> Optional[str]:
    normalized_requirement = normalize_text(requirement)
    for related in related_skills(normalized_requirement):
        evidence = _sentence_evidence(text, related)
        if evidence:
            return evidence
    return None


def classify_requirement(text: str, requirement: str, category: str) -> RequirementMatch:
    strong_evidence = _sentence_evidence(text, requirement)
    if strong_evidence:
        return RequirementMatch(requirement=requirement, category=category, status="STRONG", evidence=strong_evidence, score=100.0)
    partial_evidence = _partial_evidence(text, requirement)
    if partial_evidence:
        return RequirementMatch(requirement=requirement, category=category, status="PARTIAL", evidence=partial_evidence, score=55.0)
    return RequirementMatch(requirement=requirement, category=category, status="MISSING", evidence=None, score=0.0)


def _semantic_score(job_description: str, resume_id: int) -> float:
    rows = fetch_all("SELECT embedding FROM resume_chunks WHERE resume_id = ? ORDER BY chunk_index", (resume_id,))
    if not rows:
        return 0.0
    jd_vector = embed_texts([normalize_text(job_description)])[0]
    similarities = [
        cosine_similarity(jd_vector, deserialize_embedding(row["embedding"]))
        for row in rows
        if row.get("embedding") is not None
    ]
    if not similarities:
        return 0.0
    top = sorted(similarities, reverse=True)[:3]
    return max(0.0, min(100.0, ((float(np.mean(top)) + 1.0) / 2.0) * 100.0))


def _text_requirement_score(resume_text: str, requirements: list[str], category: str) -> tuple[float, list[RequirementMatch]]:
    matches = [classify_requirement(resume_text, requirement, category) for requirement in requirements]
    return _score_ratio(matches), matches


def _experience_score(resume_text: str, requirements: list[str]) -> float:
    if not requirements:
        return 100.0
    normalized_resume = normalize_text(resume_text)
    resume_years = [int(value) for value in re.findall(r"\b(\d+)\+?\s*(?:years|yrs)\b", normalized_resume)]
    required_years = []
    for requirement in requirements:
        required_years.extend(int(value) for value in re.findall(r"\b(\d+)\+?\s*(?:years|yrs)\b", normalize_text(requirement)))
    if required_years:
        if resume_years and max(resume_years) >= max(required_years):
            return 100.0
        if "senior" in normalized_resume or "lead" in normalized_resume:
            return 75.0
        return 35.0 if "experience" in normalized_resume else 0.0
    return 70.0 if "experience" in normalized_resume else 30.0


def _education_score(resume_text: str, requirements: list[str]) -> tuple[float, list[RequirementMatch]]:
    if not requirements:
        return 100.0, []
    matches: list[RequirementMatch] = []
    normalized_resume = normalize_text(resume_text)
    for requirement in requirements:
        normalized_requirement = normalize_text(requirement)
        if any(term in normalized_resume for term in ("bachelor", "master", "phd", "computer science", "degree")):
            evidence = next((sentence for sentence in split_sentences(resume_text) if any(term in normalize_text(sentence) for term in ("bachelor", "master", "phd", "computer science", "degree"))), None)
            status = "STRONG" if any(term in normalized_requirement for term in ("bachelor", "master", "phd", "degree")) else "PARTIAL"
            matches.append(RequirementMatch(requirement, "education", status, evidence, 100.0 if status == "STRONG" else 55.0))
        else:
            matches.append(RequirementMatch(requirement, "education", "MISSING", None, 0.0))
    return _score_ratio(matches), matches


def analyze_resume_against_job(
    resume: Dict[str, object],
    parsed_jd: ParsedJobDescription,
    job_description_id: int,
    config_hash: str,
    weights: Optional[dict[str, float]] = None,
    analysis_run_id: Optional[int] = None,
) -> tuple[dict[str, object], bool]:
    resume_id = int(resume["id"])
    index_resume(resume_id)
    cache_key = stable_hash({"resume_hash": resume["file_hash"], "job_hash": stable_hash(parsed_jd.to_dict()), "config_hash": config_hash})
    cached = fetch_one("SELECT result_json, id FROM analysis_results WHERE cache_key = ?", (cache_key,))
    if cached:
        result = json.loads(str(cached["result_json"]))
        if analysis_run_id is not None:
            execute_write("UPDATE analysis_results SET analysis_run_id = ? WHERE id = ?", (analysis_run_id, int(cached["id"])))
        return result, True

    resume_text = str(resume["extracted_text"])
    required_score, required_matches = _text_requirement_score(resume_text, parsed_jd.required_skills, "required_skill")
    preferred_score, preferred_matches = _text_requirement_score(resume_text, parsed_jd.preferred_skills, "preferred_skill")
    responsibilities_score, responsibility_matches = _text_requirement_score(resume_text, parsed_jd.responsibilities, "responsibility")
    education_score, education_matches = _education_score(resume_text, parsed_jd.education_requirements)
    experience_score = _experience_score(resume_text, parsed_jd.experience_requirements)
    semantic_score = _semantic_score(parsed_jd.description, resume_id)
    keyword_requirements = parsed_jd.required_skills + parsed_jd.preferred_skills
    keyword_matches = required_matches + preferred_matches
    keyword_coverage = (sum(1 for match in keyword_matches if match.status != "MISSING") / len(keyword_requirements)) if keyword_requirements else 0.0
    ats_report = estimate_ats_score(resume_text, keyword_coverage)
    active_weights = weights or MATCH_WEIGHTS

    overall_score = (
        required_score * active_weights["required_skills"]
        + preferred_score * active_weights["preferred_skills"]
        + semantic_score * active_weights["semantic_similarity"]
        + experience_score * active_weights["experience_match"]
        + responsibilities_score * active_weights["responsibilities"]
        + education_score * active_weights["education"]
        + ats_report.score * active_weights["ats_compatibility"]
    )
    recruiter_fit = (
        required_score * 0.45
        + preferred_score * 0.20
        + responsibilities_score * 0.15
        + experience_score * 0.10
        + semantic_score * 0.10
    )
    requirement_matches = required_matches + preferred_matches + responsibility_matches + education_matches

    result = {
        "resume_id": resume_id,
        "resume_name": resume["original_filename"],
        "overall_score": round(overall_score, 2),
        "ats_score": round(ats_report.score, 2),
        "required_skill_score": round(required_score, 2),
        "preferred_skill_score": round(preferred_score, 2),
        "semantic_score": round(semantic_score, 2),
        "experience_score": round(experience_score, 2),
        "responsibilities_score": round(responsibilities_score, 2),
        "education_score": round(education_score, 2),
        "recruiter_fit_score": round(recruiter_fit, 2),
        "ats_report": ats_report.to_dict(),
        "requirement_matches": [match.to_dict() for match in requirement_matches],
    }

    timestamp = utc_now_iso()
    result_id = execute_write(
        """
        INSERT INTO analysis_results(
            analysis_run_id, job_description_id, resume_id, cache_key,
            overall_score, ats_score, required_skill_score, preferred_skill_score,
            semantic_score, experience_score, responsibilities_score, education_score,
            recruiter_fit_score, result_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_run_id,
            job_description_id,
            resume_id,
            cache_key,
            result["overall_score"],
            result["ats_score"],
            result["required_skill_score"],
            result["preferred_skill_score"],
            result["semantic_score"],
            result["experience_score"],
            result["responsibilities_score"],
            result["education_score"],
            result["recruiter_fit_score"],
            json.dumps(result),
            timestamp,
            timestamp,
        ),
    )
    execute_many(
        """
        INSERT INTO requirement_matches(
            analysis_result_id, requirement, category, status, evidence, score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (result_id, match.requirement, match.category, match.status, match.evidence, match.score, timestamp)
            for match in requirement_matches
        ],
    )
    return result, False


def analyze_job(description: str, title: Optional[str] = None) -> dict[str, object]:
    parsed = parse_job_description(description, title)
    from .settings import get_setting

    weights = get_setting("matching_weights")
    config_hash = matching_config_hash(weights)
    description_hash = stable_hash({"title": parsed.title, "description": parsed.description})
    timestamp = utc_now_iso()
    job_description_id = execute_write(
        """
        INSERT INTO job_descriptions(title, description, description_hash, parsed_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (parsed.title, parsed.description, description_hash, json.dumps(parsed.to_dict()), timestamp),
    )

    resumes = list_resumes()
    run_id = execute_write(
        """
        INSERT INTO analysis_runs(job_description_id, config_hash, resume_count, cached_result_count, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_description_id, config_hash, len(resumes), 0, timestamp),
    )

    results: list[dict[str, object]] = []
    cached_count = 0
    for resume in resumes:
        result, cached = analyze_resume_against_job(resume, parsed, job_description_id, config_hash, weights, run_id)
        cached_count += int(cached)
        results.append(result)

    results.sort(key=lambda item: float(item["overall_score"]), reverse=True)
    for index, result in enumerate(results, start=1):
        result["rank"] = index

    execute_write("UPDATE analysis_runs SET cached_result_count = ? WHERE id = ?", (cached_count, run_id))
    return {
        "analysis_id": run_id,
        "job_description": parsed.to_dict(),
        "config_hash": config_hash,
        "cached_result_count": cached_count,
        "resume_count": len(results),
        "results": results,
    }


def get_analysis(analysis_id: int) -> Optional[dict[str, object]]:
    run = fetch_one("SELECT * FROM analysis_runs WHERE id = ?", (analysis_id,))
    if not run:
        return None
    job = fetch_one("SELECT * FROM job_descriptions WHERE id = ?", (int(run["job_description_id"]),))
    rows = fetch_all("SELECT result_json FROM analysis_results WHERE analysis_run_id = ? ORDER BY overall_score DESC", (analysis_id,))
    results = [json.loads(str(row["result_json"])) for row in rows]
    for index, result in enumerate(results, start=1):
        result["rank"] = index
    return {
        "analysis_id": analysis_id,
        "job_description": json.loads(str(job["parsed_json"])) if job else {},
        "config_hash": run["config_hash"],
        "cached_result_count": run["cached_result_count"],
        "resume_count": run["resume_count"],
        "results": results,
    }
