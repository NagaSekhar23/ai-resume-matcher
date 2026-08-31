# Recruiter Analysis

Recruiter analysis is optional and powered by a local Ollama model through an `LLMProvider` abstraction.

## Inputs

The prompt includes:

- Job description
- Structured job requirements
- Top deterministic candidates only
- Resume text for selected candidates
- Scores and requirement evidence

## Output

The backend expects structured JSON with fields such as:

- `interview_decision`: `YES`, `MAYBE`, or `NO`
- `confidence`
- `recruiter_fit_score`
- `strongest_qualifications`
- `missing_requirements`
- `partial_requirements`
- `concerns`
- `interview_reasons`
- `rejection_reasons`
- `summary`

Invalid or unavailable LLM output is handled gracefully. Deterministic ranking is still returned.

## Constraint

The recruiter analysis must not invent experience. It should only use provided resume text and evidence.
