from __future__ import annotations

from backend.app.ats import estimate_ats_score
from backend.app.database import create_resume_record, fetch_all
from backend.app.indexing import index_resume
from backend.app.matching import analyze_job, classify_requirement
from backend.app.skills import normalize_skill_name, parse_job_description


REALISTIC_JD = """
Senior Backend Engineer
Required: 5+ years experience building REST APIs with Python, FastAPI, PostgreSQL, and Docker.
Responsibilities include designing reliable services, collaborating with frontend engineers, and maintaining CI/CD pipelines.
Preferred: React, TypeScript, Kubernetes, and AWS.
Bachelor's degree in Computer Science or equivalent experience preferred.
"""


def create_resume(name: str, text: str) -> int:
    row = create_resume_record(
        filename=f"{name}.txt",
        original_filename=f"{name}.txt",
        file_type="txt",
        file_hash=f"hash-{name}",
        extracted_text=text,
    )
    return int(row["id"])


def test_jd_parsing_and_skill_normalization() -> None:
    parsed = parse_job_description(REALISTIC_JD, "Senior Backend Engineer")
    assert parsed.title == "Senior Backend Engineer"
    assert "python" in parsed.required_skills
    assert "fastapi" in parsed.required_skills
    assert "postgresql" in parsed.required_skills
    assert "react" in parsed.preferred_skills
    assert "aws" in parsed.preferred_skills
    assert parsed.experience_requirements
    assert parsed.education_requirements
    assert normalize_skill_name("Postgres") == "postgresql"
    assert normalize_skill_name("JS") == "javascript"
    assert normalize_skill_name("RESTful services") == "rest api"


def test_edge_case_invalid_job_descriptions() -> None:
    for value in ("", "Python only"):
        try:
            parse_job_description(value)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for invalid JD")


def test_jd_with_no_explicit_skills_is_supported() -> None:
    parsed = parse_job_description(
        "This role designs customer-facing systems, collaborates with teammates, improves reliability, and writes clear documentation."
    )
    assert parsed.required_skills == []
    assert parsed.responsibilities


def test_requirement_classification_strong_partial_missing() -> None:
    resume = "Skills: JavaScript, React, PostgreSQL. Built RESTful services for customers."
    assert classify_requirement(resume, "react", "required_skill").status == "STRONG"
    partial = classify_requirement(resume, "typescript", "required_skill")
    assert partial.status == "PARTIAL"
    assert partial.evidence
    missing = classify_requirement(resume, "kubernetes", "required_skill")
    assert missing.status == "MISSING"
    assert missing.evidence is None


def test_ats_scoring_uses_measurable_checks() -> None:
    resume = """
Jane Engineer
jane@example.com
Skills
Python React PostgreSQL Docker
Experience
Built APIs from 2020 to 2024.
Education
Bachelor of Science in Computer Science
"""
    report = estimate_ats_score(resume, keyword_coverage=0.8)
    assert report.score >= 80
    assert report.checks["contact_information"]
    assert report.checks["skills_section"]


def test_indexing_is_idempotent(isolated_env) -> None:
    resume_id = create_resume("idempotent", "Skills: Python FastAPI PostgreSQL Docker. Experience: Built REST APIs.")
    first = index_resume(resume_id)
    second = index_resume(resume_id)
    assert first["indexed"] is True
    assert second["indexed"] is False
    assert len(fetch_all("SELECT * FROM resume_chunks WHERE resume_id = ?", (resume_id,))) == first["chunk_count"]
    assert len(fetch_all("SELECT * FROM resume_skills WHERE resume_id = ?", (resume_id,))) >= 4


def test_weighting_ranking_caching_and_missing_skills(isolated_env) -> None:
    strong_id = create_resume(
        "backend-strong",
        """
Jane Backend Engineer
jane@example.com
Skills
Python FastAPI PostgreSQL Docker REST API CI/CD React TypeScript AWS
Experience
6 years experience designing reliable services and maintaining CI/CD pipelines from 2018 to 2026.
Education
Bachelor degree in Computer Science
""",
    )
    weak_id = create_resume(
        "frontend-partial",
        """
Frontend Developer
front@example.com
Skills
React JavaScript CSS
Experience
2 years building user interfaces.
Education
Bootcamp certificate
""",
    )
    create_resume(
        "tiny",
        "Python",
    )

    first = analyze_job(REALISTIC_JD)
    assert first["resume_count"] == 3
    assert first["cached_result_count"] == 0
    assert first["results"][0]["resume_id"] == strong_id
    assert first["results"][0]["overall_score"] > first["results"][1]["overall_score"]
    weak = next(result for result in first["results"] if result["resume_id"] == weak_id)
    kubernetes = next(match for match in weak["requirement_matches"] if match["requirement"] == "kubernetes")
    assert kubernetes["status"] == "MISSING"
    assert kubernetes["evidence"] is None

    second = analyze_job(REALISTIC_JD)
    assert second["cached_result_count"] == 3

    changed = analyze_job(REALISTIC_JD + " Required: Kubernetes operations.")
    assert changed["cached_result_count"] == 0


def test_analyze_api_and_get_analysis(client) -> None:
    create_resume(
        "api-backend",
        "api@example.com\nSkills\nPython FastAPI PostgreSQL REST API Docker\nExperience\n5 years experience building services.\nEducation\nBachelor degree",
    )
    response = client.post("/api/jobs/analyze", json={"job_title": "Backend Engineer", "job_description": REALISTIC_JD})
    assert response.status_code == 200
    payload = response.json()
    assert payload["resume_count"] == 1
    assert payload["results"][0]["requirement_matches"]

    fetched = client.get(f"/api/analyses/{payload['analysis_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["analysis_id"] == payload["analysis_id"]


def test_index_api(client) -> None:
    resume_id = create_resume("index-api", "Skills: Python FastAPI PostgreSQL. Experience: Built REST API services.")
    response = client.post(f"/api/resumes/{resume_id}/index")
    assert response.status_code == 200
    assert response.json()["indexed"] is True
    assert client.post("/api/resumes/999/index").status_code == 404
