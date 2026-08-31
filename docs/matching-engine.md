# Matching Engine

The matching engine is designed to be explainable and conservative.

## Pipeline

1. Extract text from each uploaded resume.
2. Normalize text and split it into section-aware chunks.
3. Extract known skills and aliases.
4. Parse the job description into requirement categories.
5. Compare each stored resume against the JD.
6. Cache results by resume hash, JD hash, and matching configuration.
7. Rank resumes by weighted score.

## Scores

| Score | Meaning |
| --- | --- |
| Required skills | Coverage of explicitly required JD skills. |
| Preferred skills | Coverage of preferred/nice-to-have JD skills. |
| Semantic similarity | Local embedding similarity between resume chunks and the JD. |
| Experience | Heuristic match against experience requirements. |
| Responsibilities | Evidence overlap with responsibilities. |
| Education | Evidence match for education requirements. |
| ATS compatibility | Heuristic checks for structure and extractability. |

## Evidence policy

A requirement is marked `STRONG`, `PARTIAL`, or `MISSING`. Evidence must come from resume text. If no evidence is found, the match is missing.
