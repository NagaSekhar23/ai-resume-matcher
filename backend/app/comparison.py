from __future__ import annotations

from typing import Dict, List

from .matching import get_analysis


METRICS = [
    ("overall_score", "Overall"),
    ("required_skill_score", "Required"),
    ("preferred_skill_score", "Preferred"),
    ("semantic_score", "Semantic"),
    ("ats_score", "ATS"),
]


def compare_resumes(analysis_id: int, resume_ids: List[int]) -> Dict[str, object]:
    if not 1 <= len(resume_ids) <= 3:
        raise ValueError("Select between 1 and 3 resumes to compare.")
    analysis = get_analysis(analysis_id)
    if not analysis:
        raise ValueError("Analysis not found.")
    selected = [result for result in analysis["results"] if int(result["resume_id"]) in resume_ids]
    if len(selected) != len(set(resume_ids)):
        raise ValueError("One or more selected resumes were not found in this analysis.")

    rows = []
    for key, label in METRICS:
        values = [{"resume_id": item["resume_id"], "value": item[key]} for item in selected]
        best = max(value["value"] for value in values)
        rows.append({"metric": label, "values": values, "best_value": best})

    winner = max(selected, key=lambda item: item["overall_score"])
    reasons = []
    strong_required = [match for match in winner["requirement_matches"] if match["category"] == "required_skill" and match["status"] == "STRONG"]
    missing = [match for match in winner["requirement_matches"] if match["status"] == "MISSING"]
    reasons.append(f"{winner['resume_name']} has the highest overall match at {winner['overall_score']}/100.")
    reasons.append(f"It strongly demonstrates {len(strong_required)} required skill(s).")
    if missing:
        reasons.append(f"Watch-out: {missing[0]['requirement']} is not demonstrated.")

    return {"analysis_id": analysis_id, "resumes": selected, "rows": rows, "winner": winner, "why_winner": reasons}
