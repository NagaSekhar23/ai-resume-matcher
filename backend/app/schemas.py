from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class Resume(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    file_type: str
    file_hash: str
    extracted_text: str
    created_at: str
    updated_at: str


class ResumeListResponse(BaseModel):
    resumes: list[Resume]
    count: int


class ErrorResponse(BaseModel):
    detail: str


class ResumeIndexResponse(BaseModel):
    resume_id: int
    indexed: bool
    chunk_count: int
    embedding_model: str
    skills: List[str] = []


class JobAnalyzeRequest(BaseModel):
    job_description: str
    job_title: Optional[str] = None


class RequirementMatchResponse(BaseModel):
    requirement: str
    category: str
    status: str
    evidence: Optional[str] = None
    score: float


class ATSReportResponse(BaseModel):
    score: float
    checks: Dict[str, bool]
    notes: List[str]


class ResumeAnalysisResponse(BaseModel):
    rank: Optional[int] = None
    resume_id: int
    resume_name: str
    overall_score: float
    ats_score: float
    required_skill_score: float
    preferred_skill_score: float
    semantic_score: float
    experience_score: float
    responsibilities_score: float
    education_score: float
    recruiter_fit_score: float
    ats_report: ATSReportResponse
    requirement_matches: List[RequirementMatchResponse]


class JobDescriptionResponse(BaseModel):
    title: Optional[str] = None
    description: str
    required_skills: List[str]
    preferred_skills: List[str]
    technologies: List[str]
    programming_languages: List[str]
    frameworks: List[str]
    databases: List[str]
    cloud_technologies: List[str]
    responsibilities: List[str]
    education_requirements: List[str]
    experience_requirements: List[str]


class AnalysisResponse(BaseModel):
    analysis_id: int
    job_description: JobDescriptionResponse
    config_hash: str
    cached_result_count: int
    resume_count: int
    results: List[ResumeAnalysisResponse]


class LLMStatusResponse(BaseModel):
    connected: bool
    provider: str
    model: str
    message: str


class RecruiterAssessmentResponse(BaseModel):
    available: bool
    message: str
    assessment: Optional[Dict[str, object]] = None
    candidate_count_sent: int
    fallback_summary: Optional[str] = None


class HistoryItemResponse(BaseModel):
    analysis_id: int
    job_title: str
    created_at: str
    resume_count: int
    cached_result_count: int
    recommended_resume: Optional[str] = None
    overall_score: Optional[float] = None


class SettingsResponse(BaseModel):
    theme: str
    ollama_url: str
    ollama_model: str
    matching_weights: Dict[str, float]
    embedding_model: str
    matching_config_hash: str


class SettingsUpdateRequest(BaseModel):
    theme: Optional[str] = None
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    matching_weights: Optional[Dict[str, float]] = None
    embedding_model: Optional[str] = None


class CompareRequest(BaseModel):
    resume_ids: List[int]


class CompareResponse(BaseModel):
    analysis_id: int
    resumes: List[ResumeAnalysisResponse]
    rows: List[Dict[str, object]]
    winner: ResumeAnalysisResponse
    why_winner: List[str]
