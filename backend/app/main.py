from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .config import get_settings
from .comparison import compare_resumes
from .database import create_resume_record, delete_resume, get_resume, get_resume_by_hash, init_db, list_resumes, update_resume_record, upsert_resume_fts
from .extraction import TextExtractionError, UnsupportedFileTypeError, extract_text, normalize_extension
from .history import delete_history, list_history
from .indexing import index_resume
from .llm import OllamaProvider, run_recruiter_analysis
from .matching import analyze_job, get_analysis
from .schemas import (
    AnalysisResponse,
    CompareRequest,
    CompareResponse,
    HistoryItemResponse,
    JobAnalyzeRequest,
    LLMStatusResponse,
    RecruiterAssessmentResponse,
    Resume,
    ResumeIndexResponse,
    ResumeListResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from .settings import get_settings_payload, update_settings_payload
from .storage import delete_upload, save_upload, sha256_digest, stored_filename


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="AI Resume Matcher API",
    description="Local-first resume upload and text extraction API.",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/resumes", response_model=Resume, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile = File(...)) -> Resume:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required.")

    try:
        extension = normalize_extension(file.filename, file.content_type)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    if len(file_bytes) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The uploaded file is too large.")

    file_hash = sha256_digest(file_bytes)
    duplicate = get_resume_by_hash(file_hash)
    if duplicate:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Duplicate resume already uploaded.", "resume": duplicate},
        )

    try:
        extracted_text = extract_text(file_bytes, extension)
    except TextExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    if not extracted_text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No readable text could be extracted from this resume.")

    filename = stored_filename(file_hash, extension)
    save_upload(file_bytes, filename)
    record = create_resume_record(
        filename=filename,
        original_filename=file.filename,
        file_type=extension.lstrip("."),
        file_hash=file_hash,
        extracted_text=extracted_text,
    )
    upsert_resume_fts(int(record["id"]), str(record["original_filename"]), str(record["extracted_text"]))
    index_resume(int(record["id"]))
    return Resume(**record)


@app.get("/api/resumes", response_model=ResumeListResponse)
def get_resumes() -> ResumeListResponse:
    resumes = [Resume(**record) for record in list_resumes()]
    return ResumeListResponse(resumes=resumes, count=len(resumes))


@app.get("/api/resumes/{resume_id}", response_model=Resume)
def get_resume_by_id(resume_id: int) -> Resume:
    record = get_resume(resume_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return Resume(**record)


@app.put("/api/resumes/{resume_id}", response_model=Resume)
async def replace_resume(resume_id: int, file: UploadFile = File(...)) -> Resume:
    current = get_resume(resume_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required.")

    try:
        extension = normalize_extension(file.filename, file.content_type)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    if len(file_bytes) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The uploaded file is too large.")

    file_hash = sha256_digest(file_bytes)
    duplicate = get_resume_by_hash(file_hash)
    if duplicate and int(duplicate["id"]) != resume_id:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Duplicate resume already uploaded.", "resume": duplicate},
        )

    try:
        extracted_text = extract_text(file_bytes, extension)
    except TextExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    if not extracted_text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No readable text could be extracted from this resume.")

    filename = stored_filename(file_hash, extension)
    save_upload(file_bytes, filename)
    record = update_resume_record(
        resume_id,
        filename=filename,
        original_filename=file.filename,
        file_type=extension.lstrip("."),
        file_hash=file_hash,
        extracted_text=extracted_text,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    if str(current["filename"]) != filename:
        delete_upload(str(current["filename"]))
    upsert_resume_fts(int(record["id"]), str(record["original_filename"]), str(record["extracted_text"]))
    index_resume(int(record["id"]), force=True)
    return Resume(**record)


@app.delete("/api/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_resume(resume_id: int) -> Response:
    record = delete_resume(resume_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    delete_upload(str(record["filename"]))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/resumes/{resume_id}/index", response_model=ResumeIndexResponse)
def index_resume_by_id(resume_id: int) -> ResumeIndexResponse:
    try:
        result = index_resume(resume_id, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ResumeIndexResponse(**result)


@app.post("/api/jobs/analyze", response_model=AnalysisResponse)
def analyze_job_description(payload: JobAnalyzeRequest) -> AnalysisResponse:
    try:
        result = analyze_job(payload.job_description, payload.job_title)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AnalysisResponse(**result)


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis_by_id(analysis_id: int) -> AnalysisResponse:
    result = get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    return AnalysisResponse(**result)


@app.post("/api/analyses/{analysis_id}/recruiter", response_model=RecruiterAssessmentResponse)
def recruiter_analysis_by_id(analysis_id: int) -> RecruiterAssessmentResponse:
    try:
        result = run_recruiter_analysis(analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RecruiterAssessmentResponse(**result)


@app.post("/api/analyses/{analysis_id}/compare", response_model=CompareResponse)
def compare_analysis_resumes(analysis_id: int, payload: CompareRequest) -> CompareResponse:
    try:
        result = compare_resumes(analysis_id, payload.resume_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CompareResponse(**result)


@app.get("/api/history", response_model=list[HistoryItemResponse])
def get_history() -> list[HistoryItemResponse]:
    return [HistoryItemResponse(**item) for item in list_history()]


@app.delete("/api/history/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_history(analysis_id: int) -> Response:
    if not delete_history(analysis_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/settings", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    return SettingsResponse(**get_settings_payload())


@app.put("/api/settings", response_model=SettingsResponse)
def update_app_settings(payload: SettingsUpdateRequest) -> SettingsResponse:
    updates = payload.model_dump(exclude_none=True)
    try:
        return SettingsResponse(**update_settings_payload(updates))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/api/llm/status", response_model=LLMStatusResponse)
def get_llm_status() -> LLMStatusResponse:
    status_payload = OllamaProvider().status()
    return LLMStatusResponse(**status_payload.__dict__)
