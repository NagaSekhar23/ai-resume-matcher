export type Resume = {
  id: number;
  filename: string;
  original_filename: string;
  file_type: string;
  file_hash: string;
  extracted_text: string;
  created_at: string;
  updated_at: string;
};

export type ResumeListResponse = { resumes: Resume[]; count: number };

export type ApiError = Error & { status?: number; resume?: Resume };

export type RequirementMatch = {
  requirement: string;
  category: string;
  status: 'STRONG' | 'PARTIAL' | 'MISSING';
  evidence: string | null;
  score: number;
};

export type ATSReport = { score: number; checks: Record<string, boolean>; notes: string[] };

export type ResumeAnalysis = {
  rank: number | null;
  resume_id: number;
  resume_name: string;
  overall_score: number;
  ats_score: number;
  required_skill_score: number;
  preferred_skill_score: number;
  semantic_score: number;
  experience_score: number;
  responsibilities_score: number;
  education_score: number;
  recruiter_fit_score: number;
  ats_report: ATSReport;
  requirement_matches: RequirementMatch[];
};

export type JobDescriptionAnalysis = {
  title: string | null;
  description: string;
  required_skills: string[];
  preferred_skills: string[];
  technologies: string[];
  programming_languages: string[];
  frameworks: string[];
  databases: string[];
  cloud_technologies: string[];
  responsibilities: string[];
  education_requirements: string[];
  experience_requirements: string[];
};

export type AnalysisResponse = {
  analysis_id: number;
  job_description: JobDescriptionAnalysis;
  config_hash: string;
  cached_result_count: number;
  resume_count: number;
  results: ResumeAnalysis[];
};

export type RecruiterAssessment = {
  available: boolean;
  message: string;
  assessment: null | {
    interview_decision: 'YES' | 'MAYBE' | 'NO';
    confidence: number;
    recruiter_fit_score: number;
    strongest_qualifications: string[];
    missing_requirements: string[];
    partial_requirements: string[];
    concerns: string[];
    interview_reasons: string[];
    rejection_reasons: string[];
    summary: string;
  };
  candidate_count_sent: number;
  fallback_summary: string | null;
};

export type HistoryItem = {
  analysis_id: number;
  job_title: string;
  created_at: string;
  resume_count: number;
  cached_result_count: number;
  recommended_resume: string | null;
  overall_score: number | null;
};

export type AppSettings = {
  theme: 'light' | 'dark' | 'system';
  ollama_url: string;
  ollama_model: string;
  matching_weights: Record<string, number>;
  embedding_model: string;
  matching_config_hash: string;
};

export type LLMStatus = { connected: boolean; provider: string; model: string; message: string };

export type CompareResponse = {
  analysis_id: number;
  resumes: ResumeAnalysis[];
  rows: { metric: string; values: { resume_id: number; value: number }[]; best_value: number }[];
  winner: ResumeAnalysis;
  why_winner: string[];
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

async function parseError(response: Response): Promise<ApiError> {
  let detail = `Request failed with status ${response.status}`;
  let duplicateResume: Resume | undefined;
  try {
    const payload = (await response.json()) as { detail?: string; resume?: Resume };
    detail = payload.detail ?? detail;
    duplicateResume = payload.resume;
  } catch {}
  const error = new Error(detail) as ApiError;
  error.status = response.status;
  error.resume = duplicateResume;
  return error;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function fetchResumes(): Promise<ResumeListResponse> {
  return request<ResumeListResponse>('/api/resumes', { cache: 'no-store' });
}

export async function uploadResume(file: File): Promise<Resume> {
  const formData = new FormData();
  formData.append('file', file);
  return request<Resume>('/api/resumes', { method: 'POST', body: formData });
}

export async function replaceResume(id: number, file: File): Promise<Resume> {
  const formData = new FormData();
  formData.append('file', file);
  return request<Resume>(`/api/resumes/${id}`, { method: 'PUT', body: formData });
}

export async function deleteResume(id: number): Promise<void> {
  return request<void>(`/api/resumes/${id}`, { method: 'DELETE' });
}

export async function indexResume(id: number) {
  return request<{ resume_id: number; indexed: boolean; chunk_count: number; embedding_model: string; skills: string[] }>(`/api/resumes/${id}/index`, { method: 'POST' });
}

export async function analyzeJob(jobDescription: string, jobTitle?: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>('/api/jobs/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_description: jobDescription, job_title: jobTitle || null }),
  });
}

export async function recruiterAnalysis(analysisId: number): Promise<RecruiterAssessment> {
  return request<RecruiterAssessment>(`/api/analyses/${analysisId}/recruiter`, { method: 'POST' });
}

export async function compareAnalysis(analysisId: number, resumeIds: number[]): Promise<CompareResponse> {
  return request<CompareResponse>(`/api/analyses/${analysisId}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_ids: resumeIds }),
  });
}

export async function fetchHistory(): Promise<HistoryItem[]> {
  return request<HistoryItem[]>('/api/history', { cache: 'no-store' });
}

export async function deleteHistory(analysisId: number): Promise<void> {
  return request<void>(`/api/history/${analysisId}`, { method: 'DELETE' });
}

export async function fetchSettings(): Promise<AppSettings> {
  return request<AppSettings>('/api/settings', { cache: 'no-store' });
}

export async function updateSettings(updates: Partial<AppSettings>): Promise<AppSettings> {
  return request<AppSettings>('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
}

export async function fetchLLMStatus(): Promise<LLMStatus> {
  return request<LLMStatus>('/api/llm/status', { cache: 'no-store' });
}
