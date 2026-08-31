'use client';

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react';
import {
  AnalysisResponse,
  AppSettings,
  CompareResponse,
  HistoryItem,
  LLMStatus,
  RecruiterAssessment,
  RequirementMatch,
  Resume,
  ResumeAnalysis,
  analyzeJob,
  compareAnalysis,
  deleteHistory,
  deleteResume,
  fetchHistory,
  fetchLLMStatus,
  fetchResumes,
  fetchSettings,
  indexResume,
  recruiterAnalysis,
  replaceResume,
  updateSettings,
  uploadResume,
} from '@/lib/api';

type View = 'dashboard' | 'resumes' | 'analyze' | 'history' | 'settings';
type UploadState = 'idle' | 'uploading' | 'processing' | 'success' | 'duplicate' | 'invalid' | 'parse-error' | 'error';
type StepState = 'done' | 'active' | 'idle';

const ACCEPTED_EXTENSIONS = ['pdf', 'docx', 'txt'];
const NAV: { id: View; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'resumes', label: 'Resumes' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'history', label: 'History' },
  { id: 'settings', label: 'Settings' },
];

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function matchLabel(score: number): string {
  if (score >= 80) return 'Strong Match';
  if (score >= 65) return 'Good Match';
  if (score >= 45) return 'Moderate Match';
  return 'Weak Match';
}

function scoreColor(score: number): string {
  if (score >= 80) return 'bg-green-600 dark:bg-green-500';
  if (score >= 65) return 'bg-neutral-700 dark:bg-neutral-200';
  if (score >= 45) return 'bg-amber-500';
  return 'bg-red-500';
}

function statusClass(status: RequirementMatch['status']): string {
  if (status === 'STRONG') return 'border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200';
  if (status === 'PARTIAL') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200';
  return 'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200';
}

function ScoreBar({ score, label }: { score: number; label: string }) {
  return (
    <div>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-3xl font-semibold tracking-tight text-neutral-950 dark:text-neutral-50">{Math.round(score)}</p>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-neutral-500 dark:text-neutral-400">{label}</p>
        </div>
        <p className="text-sm font-medium text-neutral-600 dark:text-neutral-300">{matchLabel(score)}</p>
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-800" aria-hidden="true">
        <div className={`h-1.5 rounded-full ${scoreColor(score)}`} style={{ width: `${Math.max(3, Math.min(100, score))}%` }} />
      </div>
    </div>
  );
}

function Section({ title, eyebrow, children }: { title: string; eyebrow?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-950">
      {eyebrow ? <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-neutral-500 dark:text-neutral-400">{eyebrow}</p> : null}
      <h2 className="text-lg font-semibold text-neutral-950 dark:text-neutral-50">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function RequirementMatrix({ matches }: { matches: RequirementMatch[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-neutral-100 text-xs uppercase tracking-[0.16em] text-neutral-500 dark:bg-neutral-900 dark:text-neutral-400">
          <tr><th className="px-4 py-3">Requirement</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Evidence</th></tr>
        </thead>
        <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
          {matches.map((match, index) => (
            <tr key={`${match.requirement}-${index}`}>
              <td className="px-4 py-3 font-medium text-neutral-950 dark:text-neutral-50">{match.requirement}</td>
              <td className="px-4 py-3"><span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${statusClass(match.status)}`}>{match.status}</span></td>
              <td className="max-w-xl px-4 py-3 text-neutral-600 dark:text-neutral-300">{match.evidence ? `“${match.evidence}”` : 'No evidence found.'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AppShell({ view, setView, children }: { view: View; setView: (view: View) => void; children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-neutral-100 text-neutral-950 dark:bg-neutral-950 dark:text-neutral-50">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col md:flex-row">
        <aside className="border-b border-neutral-200 bg-white/80 px-4 py-4 dark:border-neutral-800 dark:bg-neutral-950 md:w-64 md:border-b-0 md:border-r md:px-5">
          <div className="flex items-center justify-between md:block">
            <button onClick={() => setView('dashboard')} className="text-left text-base font-semibold tracking-tight">AI Resume Matcher</button>
            <p className="hidden text-xs text-neutral-500 dark:text-neutral-400 md:mt-2 md:block">Local resume intelligence</p>
          </div>
          <nav className="mt-4 flex gap-1 overflow-x-auto md:flex-col" aria-label="Primary navigation">
            {NAV.map((item) => (
              <button key={item.id} onClick={() => setView(item.id)} className={`rounded-lg px-3 py-2 text-left text-sm font-medium transition ${view === item.id ? 'bg-neutral-950 text-white dark:bg-neutral-100 dark:text-neutral-950' : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-950 dark:text-neutral-300 dark:hover:bg-neutral-900 dark:hover:text-white'}`}>{item.label}</button>
            ))}
          </nav>
          <div className="mt-6 hidden rounded-xl border border-neutral-200 p-3 text-xs leading-5 text-neutral-500 dark:border-neutral-800 dark:text-neutral-400 md:block">
            Private by default. Resumes, jobs, embeddings, and history stay local unless you configure local Ollama.
          </div>
        </aside>
        <div className="flex-1 px-4 py-5 sm:px-6 lg:px-8">{children}</div>
      </div>
    </main>
  );
}

function ResumeUploader({ onUploaded }: { onUploaded: (resume: Resume) => void }) {
  const [state, setState] = useState<UploadState>('idle');
  const [message, setMessage] = useState('');
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  async function handleFile(file: File) {
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!extension || !ACCEPTED_EXTENSIONS.includes(extension)) {
      setState('invalid'); setMessage('Upload a PDF, DOCX, or TXT resume.'); return;
    }
    try {
      setState('uploading'); setMessage('Uploading resume…');
      setState('processing'); setMessage('Extracting text and updating local index…');
      const resume = await uploadResume(file);
      onUploaded(resume); setState('success'); setMessage('Resume uploaded and indexed locally.');
    } catch (error) {
      const apiError = error as { status?: number; message: string; resume?: Resume };
      if (apiError.status === 409 && apiError.resume) { onUploaded(apiError.resume); setState('duplicate'); setMessage('Duplicate resume already exists.'); }
      else if (apiError.status === 422) { setState('parse-error'); setMessage(apiError.message); }
      else { setState('error'); setMessage(apiError.message); }
    } finally {
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); const file = event.dataTransfer.files[0]; if (file) void handleFile(file); }
  function onChange(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (file) void handleFile(file); }

  return (
    <div>
      <div role="button" tabIndex={0} aria-label="Upload resume" onClick={() => inputRef.current?.click()} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click(); }} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} className={`rounded-xl border border-dashed p-5 text-center transition ${dragging ? 'border-neutral-900 bg-neutral-100 dark:border-neutral-100 dark:bg-neutral-900' : 'border-neutral-300 bg-neutral-50 hover:bg-neutral-100 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:bg-neutral-800'}`}>
        <p className="font-medium">Drop resumes here</p>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">PDF, DOCX, or TXT. Indexed locally after upload.</p>
        <input ref={inputRef} type="file" accept=".pdf,.docx,.txt" onChange={onChange} className="hidden" />
      </div>
      {message ? <p role="status" className={`mt-3 rounded-lg px-3 py-2 text-sm ${state === 'success' ? 'bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200' : 'bg-neutral-100 text-neutral-700 dark:bg-neutral-900 dark:text-neutral-200'}`}>{message}</p> : null}
    </div>
  );
}

export default function ResumeDashboard() {
  const [view, setView] = useState<View>('dashboard');
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [selectedResult, setSelectedResult] = useState<ResumeAnalysis | null>(null);
  const [recruiter, setRecruiter] = useState<RecruiterAssessment | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function refresh() {
    try {
      const [resumePayload, historyPayload] = await Promise.all([fetchResumes(), fetchHistory()]);
      setResumes(resumePayload.resumes); setHistory(historyPayload); setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Unable to load local application data.');
    }
  }

  useEffect(() => {
    refresh().finally(() => setLoading(false));
    fetchSettings().then(setSettings).catch(() => undefined);
    fetchLLMStatus().then(setLlmStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const theme = settings?.theme ?? 'system';
    const dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    root.classList.toggle('dark', dark);
  }, [settings?.theme]);

  function addOrReplaceResume(resume: Resume) { setResumes((current) => [resume, ...current.filter((item) => item.id !== resume.id)]); }

  const recent = history[0];
  const best = analysis?.results[0] ?? null;

  return (
    <AppShell view={view} setView={setView}>
      {loadError ? <div role="status" className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">{loadError}</div> : null}
      {view === 'dashboard' ? <Dashboard resumes={resumes} recent={recent} setView={setView} loading={loading} /> : null}
      {view === 'resumes' ? <ResumeLibrary resumes={resumes} onUploaded={addOrReplaceResume} refresh={refresh} /> : null}
      {view === 'analyze' ? <AnalyzePage resumes={resumes} analysis={analysis} setAnalysis={setAnalysis} selectedResult={selectedResult} setSelectedResult={setSelectedResult} recruiter={recruiter} setRecruiter={setRecruiter} comparison={comparison} setComparison={setComparison} refreshHistory={refresh} /> : null}
      {view === 'history' ? <HistoryPage history={history} setHistory={setHistory} setAnalysis={setAnalysis} setView={setView} /> : null}
      {view === 'settings' ? <SettingsPage settings={settings} setSettings={setSettings} llmStatus={llmStatus} refreshStatus={() => fetchLLMStatus().then(setLlmStatus)} /> : null}
      {best && view === 'dashboard' ? <div className="mt-5"><BestResume result={best} recruiter={recruiter} /></div> : null}
    </AppShell>
  );
}

function Dashboard({ resumes, recent, setView, loading }: { resumes: Resume[]; recent?: HistoryItem; setView: (view: View) => void; loading: boolean }) {
  return (
    <div className="space-y-5">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><h1 className="text-3xl font-semibold tracking-tight">AI Resume Matcher</h1><p className="mt-2 text-neutral-600 dark:text-neutral-300">Find the strongest resume for every job.</p></div>
        <button onClick={() => setView('analyze')} className="rounded-lg bg-neutral-950 px-4 py-2.5 text-sm font-semibold text-white hover:bg-neutral-800 dark:bg-neutral-50 dark:text-neutral-950">Analyze a Job</button>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Resume Library"><p className="text-4xl font-semibold">{loading ? '—' : resumes.length}</p><p className="mt-1 text-sm text-neutral-500">resumes stored locally</p></Section>
        <Section title="Recent Analysis">{recent ? <div><p className="font-medium">{recent.job_title}</p><p className="mt-1 text-sm text-neutral-500">Recommended: {recent.recommended_resume ?? 'None'} · {Math.round(recent.overall_score ?? 0)}/100</p></div> : <p className="text-sm text-neutral-500">No analyses yet. Paste a job description to start.</p>}</Section>
      </div>
      <Section title="Recent analyses"><div className="divide-y divide-neutral-200 dark:divide-neutral-800">{recent ? <p className="py-2 text-sm">{recent.job_title} · {recent.recommended_resume}</p> : <p className="text-sm text-neutral-500">Your local history will appear here.</p>}</div></Section>
    </div>
  );
}

function ResumeLibrary({ resumes, onUploaded, refresh }: { resumes: Resume[]; onUploaded: (resume: Resume) => void; refresh: () => Promise<void> }) {
  const [query, setQuery] = useState('');
  const filtered = resumes.filter((resume) => `${resume.original_filename} ${resume.file_type} ${resume.extracted_text}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="space-y-5">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h1 className="text-3xl font-semibold tracking-tight">Your Resumes</h1><p className="mt-2 text-neutral-600 dark:text-neutral-300">Your private resume library.</p></div><button onClick={() => document.getElementById('resume-upload-card')?.scrollIntoView({ behavior: 'smooth' })} className="rounded-lg bg-neutral-950 px-4 py-2.5 text-sm font-semibold text-white dark:bg-neutral-50 dark:text-neutral-950">+ Add Resume</button></header>
      <div id="resume-upload-card"><ResumeUploader onUploaded={onUploaded} /></div>
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search resumes" aria-label="Search resumes" className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm dark:border-neutral-800 dark:bg-neutral-950" />
      <Section title="Resume library">
        {filtered.length === 0 ? <div className="rounded-xl border border-dashed border-neutral-300 p-8 text-center dark:border-neutral-700"><p className="font-medium">No resumes yet</p><p className="mt-2 text-sm text-neutral-500">Upload your resumes once. We&apos;ll index them locally so every future job analysis is fast.</p></div> : <div className="divide-y divide-neutral-200 dark:divide-neutral-800">{filtered.map((resume) => <ResumeRow key={resume.id} resume={resume} refresh={refresh} />)}</div>}
      </Section>
    </div>
  );
}

function ResumeRow({ resume, refresh }: { resume: Resume; refresh: () => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false);
  async function remove() { setBusy(true); await deleteResume(resume.id); await refresh(); setBusy(false); }
  async function reindex() { setBusy(true); await indexResume(resume.id); setBusy(false); }
  async function replace(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setBusy(true); await replaceResume(resume.id, file); await refresh(); setBusy(false); event.target.value = ''; }
  return <div className="py-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">{resume.original_filename}</p><p className="mt-1 text-sm text-neutral-500">{resume.file_type.toUpperCase()} · Indexed · Updated {formatDate(resume.updated_at)}</p></div><div className="flex flex-wrap gap-2"><button onClick={() => setOpen(!open)} className="rounded-lg border border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800">View text</button><button onClick={() => inputRef.current?.click()} className="rounded-lg border border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800">Replace</button><input ref={inputRef} type="file" accept=".pdf,.docx,.txt" onChange={(event) => void replace(event)} className="hidden" aria-label={`Replace ${resume.original_filename}`} /><button onClick={() => void reindex()} className="rounded-lg border border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800">Re-index</button><button disabled={busy} onClick={() => void remove()} className="rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:text-red-300">Delete</button></div></div>{open ? <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-neutral-100 p-3 whitespace-pre-wrap text-sm text-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">{resume.extracted_text}</pre> : null}</div>;
}

function AnalyzePage(props: { resumes: Resume[]; analysis: AnalysisResponse | null; setAnalysis: (a: AnalysisResponse) => void; selectedResult: ResumeAnalysis | null; setSelectedResult: (r: ResumeAnalysis | null) => void; recruiter: RecruiterAssessment | null; setRecruiter: (r: RecruiterAssessment | null) => void; comparison: CompareResponse | null; setComparison: (c: CompareResponse | null) => void; refreshHistory: () => Promise<void> }) {
  const [title, setTitle] = useState(''); const [jd, setJd] = useState(''); const [analyzing, setAnalyzing] = useState(false); const [error, setError] = useState('');
  const steps: { label: string; state: StepState }[] = analyzing ? [{ label: 'Reading job requirements', state: 'done' }, { label: 'Comparing required skills', state: 'done' }, { label: 'Ranking resumes', state: 'active' }, { label: 'Preparing recruiter view', state: 'idle' }] : [];
  async function run() { setError(''); setAnalyzing(true); props.setRecruiter(null); props.setComparison(null); try { const result = await analyzeJob(jd, title); props.setAnalysis(result); props.setSelectedResult(result.results[0] ?? null); await props.refreshHistory(); } catch (caught) { setError((caught as Error).message); } finally { setAnalyzing(false); } }
  return <div className="space-y-5"><header><h1 className="text-3xl font-semibold tracking-tight">Analyze a Job</h1><p className="mt-2 text-neutral-600 dark:text-neutral-300">Paste a job description. We&apos;ll find your strongest resume.</p></header><Section title="Job description"><div className="space-y-3"><label className="block text-sm font-medium">Job title <span className="text-neutral-500">optional</span><input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950" placeholder="Senior Software Engineer" /></label><label className="block text-sm font-medium">Job description<textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={10} className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950" placeholder="Paste job description here..." /></label><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><p className="text-sm text-neutral-500">Your resumes are processed locally. {props.resumes.length} resume(s) available.</p><button onClick={() => void run()} disabled={analyzing} className="rounded-lg bg-neutral-950 px-5 py-3 text-sm font-semibold text-white dark:bg-neutral-50 dark:text-neutral-950">{analyzing ? 'Analyzing…' : 'Analyze Job'}</button></div>{error ? <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p> : null}</div></Section>{analyzing ? <AnalysisProgress steps={steps} /> : null}{props.analysis ? <Results analysis={props.analysis} selected={props.selectedResult} setSelected={props.setSelectedResult} recruiter={props.recruiter} setRecruiter={props.setRecruiter} comparison={props.comparison} setComparison={props.setComparison} /> : null}</div>;
}

function AnalysisProgress({ steps }: { steps: { label: string; state: StepState }[] }) {
  return <Section title="Analyzing your resumes"><div className="space-y-2">{steps.map((step) => <p key={step.label} className="text-sm"><span className="mr-2">{step.state === 'done' ? '✓' : step.state === 'active' ? '●' : '○'}</span>{step.label}</p>)}<p className="pt-2 text-sm text-neutral-500">Previously indexed resumes make analysis faster.</p></div></Section>;
}

function Results({ analysis, selected, setSelected, recruiter, setRecruiter, comparison, setComparison }: { analysis: AnalysisResponse; selected: ResumeAnalysis | null; setSelected: (r: ResumeAnalysis) => void; recruiter: RecruiterAssessment | null; setRecruiter: (r: RecruiterAssessment | null) => void; comparison: CompareResponse | null; setComparison: (c: CompareResponse | null) => void }) {
  const best = analysis.results[0]; const [compareIds, setCompareIds] = useState<number[]>(analysis.results.slice(0, 3).map((r) => r.resume_id));
  async function runRecruiter() { setRecruiter(await recruiterAnalysis(analysis.analysis_id)); }
  async function runCompare() { setComparison(await compareAnalysis(analysis.analysis_id, compareIds)); }
  return <div className="space-y-5"><BestResume result={best} recruiter={recruiter} /><div className="flex flex-wrap gap-2"><button onClick={() => void runRecruiter()} className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-semibold dark:border-neutral-700">Run local recruiter analysis</button><button onClick={() => void runCompare()} className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-semibold dark:border-neutral-700">Compare selected resumes</button><span className="py-2 text-sm text-neutral-500">{analysis.cached_result_count} cached result(s) reused</span></div><Section title="All resumes"><div className="divide-y divide-neutral-200 dark:divide-neutral-800">{analysis.results.map((result, index) => <div key={result.resume_id} className="flex items-center justify-between gap-3 py-3"><label className="flex items-center gap-3"><input type="checkbox" checked={compareIds.includes(result.resume_id)} onChange={(e) => setCompareIds((ids) => e.target.checked ? [...ids, result.resume_id].slice(0, 3) : ids.filter((id) => id !== result.resume_id))} /><button onClick={() => setSelected(result)} className="text-left"><span className="mr-3 tabular-nums text-neutral-500">{String(index + 1).padStart(2, '0')}</span><span className="font-medium">{result.resume_name}</span></button></label><span className="text-xl font-semibold tabular-nums">{Math.round(result.overall_score)}</span></div>)}</div></Section>{selected ? <DetailedResult result={selected} /> : null}{recruiter ? <RecruiterPanel recruiter={recruiter} /> : null}{comparison ? <ComparisonPanel comparison={comparison} /> : null}</div>;
}

function BestResume({ result, recruiter }: { result: ResumeAnalysis; recruiter?: RecruiterAssessment | null }) {
  const missing = result.requirement_matches.filter((m) => m.status === 'MISSING').slice(0, 3); const strongRequired = result.requirement_matches.filter((m) => m.category === 'required_skill' && m.status === 'STRONG');
  return <Section title="Your best resume" eyebrow="Recommended"><div className="grid gap-5 lg:grid-cols-[1fr_320px]"><div><p className="text-2xl font-semibold">{result.resume_name}</p><div className="mt-5 max-w-md"><ScoreBar score={result.overall_score} label="Overall Match" /></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><ScoreBar score={result.ats_score} label="ATS Compatibility" /><ScoreBar score={result.recruiter_fit_score} label="Recruiter Fit" /><ScoreBar score={result.required_skill_score} label="Required Skills" /></div></div><div className="space-y-4"><div><p className="text-sm font-semibold uppercase tracking-[0.16em] text-neutral-500">Why this resume?</p><ul className="mt-2 space-y-1 text-sm text-neutral-700 dark:text-neutral-200"><li>Demonstrates {strongRequired.length} required requirement(s).</li><li>Ranks highest by deterministic local scoring.</li><li>Includes measurable ATS compatibility signals.</li></ul></div><div><p className="text-sm font-semibold uppercase tracking-[0.16em] text-neutral-500">Watch out for</p><ul className="mt-2 space-y-1 text-sm text-neutral-700 dark:text-neutral-200">{missing.length ? missing.map((m) => <li key={m.requirement}>{m.requirement} is not demonstrated.</li>) : <li>No missing high-priority requirements detected.</li>}</ul></div>{recruiter?.assessment ? <p className="rounded-lg bg-neutral-100 p-3 text-sm dark:bg-neutral-900">Recruiter-style decision: <strong>{recruiter.assessment.interview_decision}</strong></p> : null}</div></div></Section>;
}

function DetailedResult({ result }: { result: ResumeAnalysis }) {
  return <Section title={`${result.resume_name} detail`}><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[['Required Skills', result.required_skill_score], ['Preferred Skills', result.preferred_skill_score], ['Semantic Match', result.semantic_score], ['Experience', result.experience_score], ['Responsibilities', result.responsibilities_score], ['Education', result.education_score], ['ATS Compatibility', result.ats_score]].map(([label, value]) => <ScoreBar key={String(label)} label={String(label)} score={Number(value)} />)}</div><div className="mt-6"><RequirementMatrix matches={result.requirement_matches} /></div></Section>;
}

function RecruiterPanel({ recruiter }: { recruiter: RecruiterAssessment }) {
  if (!recruiter.available || !recruiter.assessment) return <Section title="AI-assisted recruiter-style assessment"><p className="text-sm text-neutral-600 dark:text-neutral-300">{recruiter.fallback_summary ?? recruiter.message}</p></Section>;
  const a = recruiter.assessment;
  return <Section title="Would I interview you?" eyebrow="AI-assisted recruiter-style assessment"><div className="grid gap-4 md:grid-cols-3"><ScoreBar score={a.recruiter_fit_score} label="Recruiter Fit" /><ScoreBar score={a.confidence} label="Confidence" /><div><p className="text-4xl font-semibold">{a.interview_decision}</p><p className="mt-2 text-sm text-neutral-500">Decision is AI-assisted, not a guarantee from an actual recruiter.</p></div></div><div className="mt-5 grid gap-4 md:grid-cols-2"><div><p className="font-semibold">Why</p><ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{a.interview_reasons.map((r) => <li key={r}>{r}</li>)}</ol></div><div><p className="font-semibold">Concerns</p><ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{a.concerns.map((r) => <li key={r}>{r}</li>)}</ol></div></div><p className="mt-4 text-sm text-neutral-600 dark:text-neutral-300">{a.summary}</p></Section>;
}

function ComparisonPanel({ comparison }: { comparison: CompareResponse }) {
  return <Section title={`Why ${comparison.winner.resume_name} wins`}><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr><th className="py-2 text-left">Metric</th>{comparison.resumes.map((r) => <th key={r.resume_id} className="px-3 py-2 text-right">{r.resume_name}</th>)}</tr></thead><tbody>{comparison.rows.map((row) => <tr key={row.metric} className="border-t border-neutral-200 dark:border-neutral-800"><td className="py-2 font-medium">{row.metric}</td>{comparison.resumes.map((r) => { const value = row.values.find((v) => v.resume_id === r.resume_id)?.value ?? 0; return <td key={r.resume_id} className={`px-3 py-2 text-right tabular-nums ${value === row.best_value ? 'font-bold text-green-700 dark:text-green-300' : ''}`}>{Math.round(value)}</td>; })}</tr>)}</tbody></table></div><ul className="mt-4 space-y-1 text-sm text-neutral-700 dark:text-neutral-200">{comparison.why_winner.map((reason) => <li key={reason}>{reason}</li>)}</ul></Section>;
}

function HistoryPage({ history, setHistory, setAnalysis, setView }: { history: HistoryItem[]; setHistory: (h: HistoryItem[]) => void; setAnalysis: (a: AnalysisResponse) => void; setView: (v: View) => void }) {
  async function remove(id: number) { await deleteHistory(id); setHistory(history.filter((item) => item.analysis_id !== id)); }
  return <div className="space-y-5"><header><h1 className="text-3xl font-semibold tracking-tight">History</h1><p className="mt-2 text-neutral-600 dark:text-neutral-300">Previous analyses stored locally.</p></header><Section title="Analysis history">{history.length === 0 ? <p className="text-sm text-neutral-500">No history yet.</p> : <div className="divide-y divide-neutral-200 dark:divide-neutral-800">{history.map((item) => <div key={item.analysis_id} className="flex items-center justify-between gap-3 py-3"><button onClick={async () => { const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'}/api/analyses/${item.analysis_id}`); setAnalysis(await response.json()); setView('analyze'); }} className="text-left"><p className="font-medium">{item.job_title}</p><p className="text-sm text-neutral-500">{formatDate(item.created_at)} · Recommended: {item.recommended_resume ?? 'None'} · {Math.round(item.overall_score ?? 0)}/100</p></button><button onClick={() => void remove(item.analysis_id)} className="rounded-lg border border-red-200 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:text-red-300">Delete</button></div>)}</div>}</Section></div>;
}

function SettingsPage({ settings, setSettings, llmStatus, refreshStatus }: { settings: AppSettings | null; setSettings: (s: AppSettings) => void; llmStatus: LLMStatus | null; refreshStatus: () => Promise<void> }) {
  const [draft, setDraft] = useState<AppSettings | null>(settings); const [message, setMessage] = useState('');
  useEffect(() => setDraft(settings), [settings]);
  if (!draft) return <Section title="Settings"><p className="text-sm text-neutral-500">Loading settings…</p></Section>;
  const total = Object.values(draft.matching_weights).reduce((sum, value) => sum + value, 0);
  async function save() { if (!draft) return; try { const updated = await updateSettings(draft); setSettings(updated); setMessage('Settings saved.'); } catch (e) { setMessage((e as Error).message); } }
  return <div className="space-y-5"><header><h1 className="text-3xl font-semibold tracking-tight">Settings</h1><p className="mt-2 text-neutral-600 dark:text-neutral-300">Keep advanced controls away from the main workflow.</p></header><Section title="General"><label className="text-sm font-medium">Theme<select value={draft.theme} onChange={(e) => setDraft({ ...draft, theme: e.target.value as AppSettings['theme'] })} className="mt-2 block rounded-lg border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label></Section><Section title="AI"><div className="grid gap-3 md:grid-cols-2"><label className="text-sm font-medium">Ollama URL<input value={draft.ollama_url} onChange={(e) => setDraft({ ...draft, ollama_url: e.target.value })} className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950" /></label><label className="text-sm font-medium">Model<input value={draft.ollama_model} onChange={(e) => setDraft({ ...draft, ollama_model: e.target.value })} className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950" /></label></div><p className="mt-3 text-sm"><span className={llmStatus?.connected ? 'text-green-700 dark:text-green-300' : 'text-neutral-500'}>{llmStatus?.connected ? '● Connected' : '○ Not connected'}</span> {llmStatus?.message}</p><button onClick={() => void refreshStatus()} className="mt-3 rounded-lg border border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800">Check connection</button></Section><Section title="Matching"><div className="space-y-2">{Object.entries(draft.matching_weights).map(([key, value]) => <label key={key} className="flex items-center justify-between gap-3 text-sm"><span>{key.replaceAll('_', ' ')}</span><input type="number" min="0" max="100" value={Math.round(value * 100)} onChange={(e) => setDraft({ ...draft, matching_weights: { ...draft.matching_weights, [key]: Number(e.target.value) / 100 } })} className="w-24 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-right dark:border-neutral-800 dark:bg-neutral-950" /></label>)}<p className={`text-sm ${Math.round(total * 100) === 100 ? 'text-neutral-500' : 'text-red-600'}`}>Total: {Math.round(total * 100)}%</p></div></Section><Section title="Advanced"><p className="text-sm text-neutral-600 dark:text-neutral-300">Embedding model: {draft.embedding_model}</p><p className="mt-2 text-sm text-neutral-600 dark:text-neutral-300">Storage: local project `data/` folder.</p></Section><Section title="Privacy"><p className="text-sm leading-6 text-neutral-600 dark:text-neutral-300">Your resumes, job descriptions, embeddings, and analysis history are stored locally. Deterministic matching and default embeddings run locally. Ollama runs locally when configured. No external AI API is required.</p></Section><button onClick={() => void save()} className="rounded-lg bg-neutral-950 px-4 py-2.5 text-sm font-semibold text-white dark:bg-neutral-50 dark:text-neutral-950">Save settings</button>{message ? <p role="status" className="text-sm text-neutral-500">{message}</p> : null}</div>;
}
