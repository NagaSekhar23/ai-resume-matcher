import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Resume } from '@/lib/api';
import ResumeDashboard from './ResumeDashboard';

const resume = {
  id: 1,
  filename: 'hash.pdf',
  original_filename: 'resume.pdf',
  file_type: 'pdf',
  file_hash: 'hash',
  extracted_text: 'Jane Candidate built APIs with Python and React experience.',
  created_at: '2026-08-31T12:00:00+00:00',
  updated_at: '2026-08-31T12:00:00+00:00',
};

const settings = {
  theme: 'system',
  ollama_url: 'http://localhost:11434',
  ollama_model: 'mistral:latest',
  matching_weights: {
    required_skills: 0.35,
    preferred_skills: 0.2,
    semantic_similarity: 0.15,
    experience_match: 0.1,
    responsibilities: 0.1,
    education: 0.05,
    ats_compatibility: 0.05,
  },
  embedding_model: 'local-hashing-embedding-v1',
  matching_config_hash: 'config',
};

function analysisPayload() {
  return {
    analysis_id: 1,
    job_description: {
      title: 'Backend Engineer',
      description: 'Need Python and React.',
      required_skills: ['python'],
      preferred_skills: ['react'],
      technologies: [],
      programming_languages: ['python'],
      frameworks: ['react'],
      databases: [],
      cloud_technologies: [],
      responsibilities: [],
      education_requirements: [],
      experience_requirements: [],
    },
    config_hash: 'config',
    cached_result_count: 0,
    resume_count: 1,
    results: [{
      rank: 1,
      resume_id: 1,
      resume_name: 'resume.pdf',
      overall_score: 91,
      ats_score: 88,
      required_skill_score: 100,
      preferred_skill_score: 100,
      semantic_score: 80,
      experience_score: 80,
      responsibilities_score: 100,
      education_score: 100,
      recruiter_fit_score: 92,
      ats_report: { score: 88, checks: { skills_section: true }, notes: [] },
      requirement_matches: [
        { requirement: 'python', category: 'required_skill', status: 'STRONG', evidence: 'Built APIs with Python.', score: 100 },
        { requirement: 'react', category: 'preferred_skill', status: 'STRONG', evidence: 'Built UIs with React.', score: 100 },
      ],
    }],
  };
}

function mockFetch(resumes: Resume[] = [], count = 0) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes('/api/history')) return Response.json([]);
    if (url.includes('/api/settings')) return Response.json(settings);
    if (url.includes('/api/llm/status')) return Response.json({ connected: false, provider: 'ollama', model: 'mistral:latest', message: 'Not connected' });
    if (url.includes('/api/jobs/analyze')) return Response.json(analysisPayload());
    if (url.includes('/api/analyses/1/recruiter')) return Response.json({
      available: true,
      message: 'AI-assisted recruiter-style assessment generated locally.',
      candidate_count_sent: 1,
      fallback_summary: null,
      assessment: {
        interview_decision: 'YES',
        confidence: 91,
        recruiter_fit_score: 87,
        strongest_qualifications: ['Python APIs'],
        missing_requirements: [],
        partial_requirements: ['React'],
        concerns: ['Limited cloud evidence'],
        interview_reasons: ['Strong Python evidence'],
        rejection_reasons: [],
        summary: 'Strong evidence-backed fit.',
      },
    });
    if (url.includes('/api/resumes/1/index')) return Response.json({ resume_id: 1, indexed: true, chunk_count: 1, embedding_model: 'local', skills: ['python'] });
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
    return Response.json({ resumes, count });
  }));
}

afterEach(() => vi.restoreAllMocks());

test('renders premium shell and dashboard workflow', async () => {
  mockFetch([], 0);
  render(<ResumeDashboard />);
  expect(await screen.findByRole('heading', { name: 'AI Resume Matcher' })).toBeInTheDocument();
  expect(screen.getByText('Find the strongest resume for every job.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Analyze a Job' })).toBeInTheDocument();
});

test('shows resume library empty state and upload controls', async () => {
  mockFetch([], 0);
  render(<ResumeDashboard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Resumes' }));
  expect(screen.getByText('No resumes yet')).toBeInTheDocument();
  expect(screen.getByLabelText('Upload resume')).toBeInTheDocument();
});

test('lists uploaded resumes, views text, re-indexes and deletes one', async () => {
  mockFetch([resume], 1);
  render(<ResumeDashboard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Resumes' }));
  expect(await screen.findByText('resume.pdf')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'View text' }));
  expect(screen.getByText(/Jane Candidate built APIs/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Re-index' }));
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
});

test('shows invalid file state before upload', async () => {
  mockFetch([], 0);
  render(<ResumeDashboard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Resumes' }));
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, new File(['hello'], 'resume.png', { type: 'image/png' }), { applyAccept: false });
  expect(await screen.findByText(/Upload a PDF, DOCX, or TXT/)).toBeInTheDocument();
});

test('analyzes a job description and shows ranked evidence', async () => {
  mockFetch([resume], 1);
  render(<ResumeDashboard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Analyze' }));
  await userEvent.type(screen.getByPlaceholderText('Senior Software Engineer'), 'Backend Engineer');
  await userEvent.type(screen.getByPlaceholderText('Paste job description here...'), 'Required: Python. Preferred: React. Build services with 5 years experience.');
  await userEvent.click(screen.getByRole('button', { name: 'Analyze Job' }));
  expect(await screen.findByText('Recommended')).toBeInTheDocument();
  expect(screen.getByText(/Built APIs with Python/)).toBeInTheDocument();
});

test('shows local recruiter analysis in the UI', async () => {
  mockFetch([resume], 1);
  render(<ResumeDashboard />);
  await userEvent.click(await screen.findByRole('button', { name: 'Analyze' }));
  await userEvent.type(screen.getByPlaceholderText('Paste job description here...'), 'Required: Python. Preferred: React.');
  await userEvent.click(screen.getByRole('button', { name: 'Analyze Job' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Run local recruiter analysis' }));
  expect(await screen.findByText('Would I interview you?')).toBeInTheDocument();
  expect(screen.getAllByText('YES').length).toBeGreaterThan(0);
  expect(screen.getByText('Strong evidence-backed fit.')).toBeInTheDocument();
});
