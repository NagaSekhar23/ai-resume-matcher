from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from .database import execute_write, fetch_one
from .matching import get_analysis
from .settings import get_setting

MAX_JD_CHARS_FOR_LLM = 900
MAX_REQUIREMENTS_FOR_LLM = 8
MAX_EVIDENCE_ROWS_PER_CANDIDATE = 4
MAX_EVIDENCE_CHARS_FOR_LLM = 240


class RecruiterAssessment(BaseModel):
    interview_decision: str
    confidence: int = Field(ge=0, le=100)
    recruiter_fit_score: int = Field(ge=0, le=100)
    strongest_qualifications: List[str]
    missing_requirements: List[str]
    partial_requirements: List[str]
    concerns: List[str]
    interview_reasons: List[str]
    rejection_reasons: List[str]
    summary: str

    @field_validator("interview_decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"YES", "MAYBE", "NO"}:
            raise ValueError("interview_decision must be YES, MAYBE, or NO.")
        return normalized


def parse_recruiter_json(body: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Ollama returned invalid JSON.")
    try:
        parsed = json.loads(body[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Ollama returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Ollama returned invalid JSON.")
    return parsed


def normalize_recruiter_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    if "interview_decision" not in normalized and "decision" in normalized:
        normalized["interview_decision"] = normalized["decision"]

    score = normalized.get("recruiter_fit_score", normalized.get("confidence", 50))
    try:
        score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        score = 50
    normalized["recruiter_fit_score"] = score

    confidence = normalized.get("confidence", score)
    try:
        confidence = max(0, min(100, int(confidence)))
    except (TypeError, ValueError):
        confidence = score
    if confidence == 0 and score > 0:
        confidence = score
    normalized["confidence"] = confidence

    decision = str(normalized.get("interview_decision") or "").upper()
    if decision not in {"YES", "MAYBE", "NO"}:
        decision = "YES" if score >= 80 else "MAYBE" if score >= 60 else "NO"
    normalized["interview_decision"] = decision

    for key in (
        "strongest_qualifications",
        "missing_requirements",
        "partial_requirements",
        "concerns",
        "interview_reasons",
        "rejection_reasons",
    ):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = [value]
        elif isinstance(value, list):
            items = []
            for item in value[:5]:
                if isinstance(item, dict):
                    label = item.get("requirement") or item.get("skill") or item.get("name") or "Requirement"
                    evidence = item.get("evidence")
                    items.append(f"{label}: {evidence}" if evidence else str(label))
                else:
                    items.append(str(item))
            normalized[key] = items
        else:
            normalized[key] = []

    if not isinstance(normalized.get("summary"), str) or not normalized["summary"].strip():
        normalized["summary"] = "Local recruiter-style analysis completed using the provided match evidence."
    return normalized


def guard_assessment_with_evidence(assessment: RecruiterAssessment, analysis: Dict[str, Any]) -> RecruiterAssessment:
    if not analysis.get("results"):
        return assessment

    best = analysis["results"][0]
    matches = best.get("requirement_matches", [])
    strong = [match for match in matches if match.get("status") == "STRONG" and match.get("evidence")]
    partial = [match for match in matches if match.get("status") == "PARTIAL"]
    missing = [match for match in matches if match.get("status") == "MISSING"]

    strongest = [f"{match['requirement']}: {match['evidence']}" for match in strong[:5]]
    missing_requirements = [f"{match['requirement']}: No evidence found." for match in missing[:5]]
    partial_requirements = [
        f"{match['requirement']}: {match.get('evidence') or 'Only partial evidence found.'}" for match in partial[:5]
    ]
    concerns = []
    if missing:
        concerns.append("Missing evidence for: " + ", ".join(str(match["requirement"]) for match in missing[:4]) + ".")
    if partial:
        concerns.append("Partial evidence for: " + ", ".join(str(match["requirement"]) for match in partial[:4]) + ".")
    interview_reasons = [
        f"{match['requirement']} is supported by resume evidence." for match in strong[:3]
    ] or assessment.interview_reasons
    rejection_reasons = [
        f"{match['requirement']} has no supporting resume evidence." for match in missing[:3]
    ]

    demonstrated = ", ".join(str(match["requirement"]) for match in strong[:4]) or "the strongest matched requirements"
    watch = ", ".join(str(match["requirement"]) for match in (missing + partial)[:4])
    summary = f"Based only on extracted evidence, {best['resume_name']} is strongest for {demonstrated}."
    if watch:
        summary += f" Watch areas: {watch}."

    return RecruiterAssessment(
        interview_decision=assessment.interview_decision,
        confidence=assessment.confidence,
        recruiter_fit_score=assessment.recruiter_fit_score,
        strongest_qualifications=strongest or assessment.strongest_qualifications,
        missing_requirements=missing_requirements,
        partial_requirements=partial_requirements,
        concerns=concerns,
        interview_reasons=interview_reasons,
        rejection_reasons=rejection_reasons,
        summary=summary,
    )


@dataclass(frozen=True)
class LLMStatus:
    connected: bool
    provider: str
    model: str
    message: str


class LLMProvider(Protocol):
    def status(self) -> LLMStatus:
        ...

    def recruiter_analysis(self, prompt: str, timeout_seconds: float = 120.0) -> RecruiterAssessment:
        ...


class OllamaProvider:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None) -> None:
        self.base_url = (base_url or get_setting("ollama_url")).rstrip("/")
        self.model = model or get_setting("ollama_model")

    def status(self) -> LLMStatus:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3, trust_env=False)
            response.raise_for_status()
            models = [item.get("name") for item in response.json().get("models", [])]
            if self.model in models or not models:
                return LLMStatus(True, "ollama", self.model, "Connected")
            return LLMStatus(False, "ollama", self.model, f"Connected, but model '{self.model}' was not found.")
        except Exception as exc:
            return LLMStatus(False, "ollama", self.model, f"Not connected: {exc}")

    def recruiter_analysis(self, prompt: str, timeout_seconds: float = 120.0) -> RecruiterAssessment:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"num_predict": 280, "temperature": 0.1},
            },
            timeout=timeout_seconds,
            trust_env=False,
        )
        response.raise_for_status()
        body = response.json().get("response", "")
        try:
            parsed = parse_recruiter_json(body)
            return RecruiterAssessment(**normalize_recruiter_payload(parsed))
        except ValidationError as exc:
            raise ValueError("Ollama JSON did not match the recruiter schema.") from exc


def build_recruiter_prompt(analysis: Dict[str, Any], top_n: int = 3) -> str:
    candidates = analysis["results"][:top_n]
    compact = []
    for candidate in candidates:
        requirement_evidence = []
        for match in candidate["requirement_matches"]:
            if len(requirement_evidence) >= MAX_EVIDENCE_ROWS_PER_CANDIDATE:
                break
            if match["status"] != "MISSING" or match["category"] == "required":
                requirement_evidence.append(
                    {
                        "requirement": match["requirement"],
                        "category": match["category"],
                        "status": match["status"],
                        "evidence": match["evidence"][:MAX_EVIDENCE_CHARS_FOR_LLM] if match["evidence"] else None,
                    }
                )
        compact.append(
            {
                "resume_name": candidate["resume_name"],
                "scores": {
                    "overall": candidate["overall_score"],
                    "required": candidate["required_skill_score"],
                    "ats": candidate["ats_score"],
                    "recruiter_fit": candidate["recruiter_fit_score"],
                },
                "requirement_evidence": requirement_evidence,
            }
        )
    job = analysis["job_description"]
    compact_job = {
        "title": job.get("title"),
        "description_excerpt": job.get("description", "")[:MAX_JD_CHARS_FOR_LLM],
        "required_skills": job.get("required_skills", [])[:MAX_REQUIREMENTS_FOR_LLM],
        "preferred_skills": job.get("preferred_skills", [])[:MAX_REQUIREMENTS_FOR_LLM],
        "responsibilities": job.get("responsibilities", [])[:MAX_REQUIREMENTS_FOR_LLM],
        "education_requirements": job.get("education_requirements", [])[:MAX_REQUIREMENTS_FOR_LLM],
        "experience_requirements": job.get("experience_requirements", [])[:MAX_REQUIREMENTS_FOR_LLM],
    }
    return (
        "You are a local recruiter-style resume reviewer. Use only the provided evidence. "
        "Never invent skills, experience, companies, years, or accomplishments. "
        "Return only valid JSON with keys: interview_decision, confidence, recruiter_fit_score, "
        "strongest_qualifications, missing_requirements, partial_requirements, concerns, "
        "interview_reasons, rejection_reasons, summary. Keep arrays to 2 items each and summary to 1 sentence. "
        "Return JSON only, no markdown.\n\n"
        + json.dumps({"job_description": compact_job, "top_candidates": compact}, ensure_ascii=False)
    )


def fallback_assessment(analysis: Dict[str, Any], message: str) -> Dict[str, Any]:
    best = analysis["results"][0] if analysis["results"] else None
    return {
        "available": False,
        "message": message,
        "assessment": None,
        "candidate_count_sent": 0,
        "fallback_summary": (
            f"Local AI analysis unavailable. Deterministic ranking is still available; best resume is {best['resume_name']}."
            if best
            else "Local AI analysis unavailable. Upload resumes and analyze a job to see deterministic ranking."
        ),
    }


def run_recruiter_analysis(analysis_id: int, provider: Optional[LLMProvider] = None, top_n: int = 3) -> Dict[str, Any]:
    analysis = get_analysis(analysis_id)
    if not analysis:
        raise ValueError("Analysis not found.")
    cached = fetch_one("SELECT recruiter_result_json FROM analysis_runs WHERE id = ?", (analysis_id,))
    if cached and cached.get("recruiter_result_json"):
        return json.loads(str(cached["recruiter_result_json"]))

    provider = provider or OllamaProvider()
    status = provider.status()
    if not status.connected:
        result = fallback_assessment(analysis, "Local AI analysis unavailable. Your resume ranking is still available.")
        return result

    prompt = build_recruiter_prompt(analysis, top_n=min(top_n, 5))
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            assessment = guard_assessment_with_evidence(provider.recruiter_analysis(prompt), analysis)
            result = {
                "available": True,
                "message": "AI-assisted recruiter-style assessment generated locally.",
                "assessment": assessment.model_dump(),
                "candidate_count_sent": min(len(analysis["results"]), top_n, 5),
                "fallback_summary": None,
            }
            break
        except httpx.TimeoutException as exc:
            last_error = exc
            break
        except Exception as exc:
            last_error = exc
            if attempt == 1:
                break
    else:
        result = fallback_assessment(analysis, "Local AI analysis unavailable.")
    if "result" not in locals():
        result = fallback_assessment(analysis, f"Local AI analysis unavailable: {last_error}")
    if result["available"]:
        execute_write("UPDATE analysis_runs SET recruiter_result_json = ? WHERE id = ?", (json.dumps(result), analysis_id))
    return result
