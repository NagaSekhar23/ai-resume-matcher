from __future__ import annotations

from typing import List

import httpx
import pytest

from backend.app.comparison import compare_resumes
from backend.app.database import create_resume_record
from backend.app.llm import RecruiterAssessment, build_recruiter_prompt, guard_assessment_with_evidence, normalize_recruiter_payload, parse_recruiter_json, run_recruiter_analysis
from backend.app.matching import analyze_job
from backend.app.settings import update_settings_payload, validate_weights


JD = """
Senior Software Engineer
Required: 5+ years experience building REST APIs with Python, FastAPI, PostgreSQL, and Docker.
Responsibilities include designing reliable services and maintaining CI/CD pipelines.
Preferred: React, TypeScript, Kubernetes, and AWS.
Bachelor degree in Computer Science preferred.
"""


class UnavailableProvider:
    def status(self):
        return type("Status", (), {"connected": False, "provider": "ollama", "model": "test", "message": "Not connected"})()

    def recruiter_analysis(self, prompt: str, timeout_seconds: float = 20.0):
        raise AssertionError("Should not call unavailable provider")


class TimeoutProvider:
    def status(self):
        return type("Status", (), {"connected": True, "provider": "ollama", "model": "test", "message": "Connected"})()

    def recruiter_analysis(self, prompt: str, timeout_seconds: float = 20.0):
        raise httpx.TimeoutException("timed out")


class ValidProvider:
    prompts: List[str] = []

    def status(self):
        return type("Status", (), {"connected": True, "provider": "ollama", "model": "test", "message": "Connected"})()

    def recruiter_analysis(self, prompt: str, timeout_seconds: float = 20.0):
        self.prompts.append(prompt)
        return RecruiterAssessment(
            interview_decision="YES",
            confidence=88,
            recruiter_fit_score=86,
            strongest_qualifications=["Python and FastAPI evidence"],
            missing_requirements=["Kubernetes"],
            partial_requirements=["TypeScript"],
            concerns=["Kubernetes is missing"],
            interview_reasons=["Strong required skill match"],
            rejection_reasons=[],
            summary="Strong local deterministic match with supported evidence.",
        )


class FlakyProvider:
    calls = 0

    def status(self):
        return type("Status", (), {"connected": True, "provider": "ollama", "model": "test", "message": "Connected"})()

    def recruiter_analysis(self, prompt: str, timeout_seconds: float = 120.0):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("Ollama returned invalid JSON.")
        return RecruiterAssessment(
            interview_decision="MAYBE",
            confidence=70,
            recruiter_fit_score=68,
            strongest_qualifications=["Python evidence"],
            missing_requirements=[],
            partial_requirements=[],
            concerns=[],
            interview_reasons=["Evidence exists"],
            rejection_reasons=[],
            summary="Recovered after retry.",
        )


def make_resume(name: str, text: str) -> int:
    row = create_resume_record(
        filename=f"{name}.txt",
        original_filename=f"{name}.txt",
        file_type="txt",
        file_hash=f"final-{name}",
        extracted_text=text,
    )
    return int(row["id"])


def seed_resumes(count: int = 5) -> None:
    make_resume("backend", "backend@example.com\nSkills\nPython FastAPI PostgreSQL Docker REST API React\nExperience\n6 years experience building APIs.\nEducation\nBachelor degree")
    for index in range(1, count):
        make_resume(f"resume-{index}", f"user{index}@example.com\nSkills\nJavaScript React CSS\nExperience\n{index} years building UI.\nEducation\nBootcamp")


def test_weight_validation_and_settings(isolated_env) -> None:
    valid = validate_weights({
        "required_skills": 0.35,
        "preferred_skills": 0.20,
        "semantic_similarity": 0.15,
        "experience_match": 0.10,
        "responsibilities": 0.10,
        "education": 0.05,
        "ats_compatibility": 0.05,
    })
    assert sum(valid.values()) == 1.0
    with pytest.raises(ValueError):
        validate_weights({**valid, "required_skills": 0.5})
    updated = update_settings_payload({"theme": "dark", "ollama_model": "mistral:latest"})
    assert updated["theme"] == "dark"


def test_history_settings_compare_api(client) -> None:
    seed_resumes(3)
    analysis = client.post("/api/jobs/analyze", json={"job_title": "Software Engineer", "job_description": JD}).json()
    history = client.get("/api/history")
    assert history.status_code == 200
    assert history.json()[0]["recommended_resume"]
    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["matching_config_hash"]
    compare = client.post(
        f"/api/analyses/{analysis['analysis_id']}/compare",
        json={"resume_ids": [item["resume_id"] for item in analysis["results"][:3]]},
    )
    assert compare.status_code == 200
    assert compare.json()["winner"]["resume_name"].endswith("backend.txt")
    delete = client.delete(f"/api/history/{analysis['analysis_id']}")
    assert delete.status_code == 204


def test_ollama_unavailable_fallback(isolated_env) -> None:
    seed_resumes(5)
    analysis = analyze_job(JD)
    result = run_recruiter_analysis(int(analysis["analysis_id"]), provider=UnavailableProvider())
    assert result["available"] is False
    assert "ranking is still available" in result["message"]


def test_llm_timeout_fallback(isolated_env) -> None:
    seed_resumes(5)
    analysis = analyze_job(JD)
    result = run_recruiter_analysis(int(analysis["analysis_id"]), provider=TimeoutProvider())
    assert result["available"] is False
    assert result["fallback_summary"]


def test_valid_llm_json_and_top_candidate_limit(isolated_env) -> None:
    seed_resumes(8)
    analysis = analyze_job(JD)
    provider = ValidProvider()
    result = run_recruiter_analysis(int(analysis["analysis_id"]), provider=provider, top_n=3)
    assert result["available"] is True
    assert result["assessment"]["interview_decision"] == "YES"
    assert result["candidate_count_sent"] == 3
    prompt_payload = provider.prompts[0]
    assert prompt_payload.count("resume_name") == 3


def test_llm_invalid_json_retries_once(isolated_env) -> None:
    seed_resumes(5)
    analysis = analyze_job(JD)
    provider = FlakyProvider()
    result = run_recruiter_analysis(int(analysis["analysis_id"]), provider=provider)
    assert result["available"] is True
    assert provider.calls == 2


def test_recruiter_payload_normalization() -> None:
    normalized = normalize_recruiter_payload({
        "decision": "interview",
        "confidence": "91",
        "recruiter_fit_score": "84",
        "strongest_qualifications": [{"skill": "Python", "evidence": "Built Python APIs."}],
    })
    assert normalized["interview_decision"] == "YES"
    assert normalized["confidence"] == 91
    assert normalized["strongest_qualifications"] == ["Python: Built Python APIs."]


def test_recruiter_json_parser_accepts_wrapped_json() -> None:
    parsed = parse_recruiter_json('Here is the JSON: {"interview_decision":"MAYBE","confidence":70}')
    assert parsed["interview_decision"] == "MAYBE"
    assert parsed["confidence"] == 70


def test_recruiter_guard_prevents_evidence_contradictions() -> None:
    raw = RecruiterAssessment(
        interview_decision="MAYBE",
        confidence=75,
        recruiter_fit_score=70,
        strongest_qualifications=["Generic strength"],
        missing_requirements=["python"],
        partial_requirements=[],
        concerns=["No Python evidence."],
        interview_reasons=["Generic reason"],
        rejection_reasons=[],
        summary="Candidate lacks Python.",
    )
    guarded = guard_assessment_with_evidence(raw, {
        "results": [{
            "resume_name": "backend.txt",
            "requirement_matches": [
                {"requirement": "python", "status": "STRONG", "evidence": "Built Python APIs."},
                {"requirement": "kubernetes", "status": "MISSING", "evidence": None},
            ],
        }]
    })
    assert guarded.missing_requirements == ["kubernetes: No evidence found."]
    assert guarded.strongest_qualifications == ["python: Built Python APIs."]
    assert "lacks Python" not in guarded.summary


def test_comparison_limits(isolated_env) -> None:
    seed_resumes(4)
    analysis = analyze_job(JD)
    with pytest.raises(ValueError):
        compare_resumes(int(analysis["analysis_id"]), [item["resume_id"] for item in analysis["results"][:4]])


def test_recruiter_prompt_uses_evidence_only(isolated_env) -> None:
    seed_resumes(5)
    analysis = analyze_job(JD)
    prompt = build_recruiter_prompt(analysis, top_n=3)
    assert "Never invent skills" in prompt
    assert "requirement_evidence" in prompt
