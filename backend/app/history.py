from __future__ import annotations

import json
from typing import Dict, List, Optional

from .database import execute_write, fetch_all, fetch_one


def list_history() -> List[Dict[str, object]]:
    rows = fetch_all(
        """
        SELECT
            ar.id,
            jd.title,
            jd.created_at,
            ar.resume_count,
            ar.cached_result_count,
            best.resume_id,
            best.overall_score,
            best.result_json
        FROM analysis_runs ar
        JOIN job_descriptions jd ON jd.id = ar.job_description_id
        LEFT JOIN analysis_results best ON best.id = (
            SELECT id FROM analysis_results
            WHERE analysis_run_id = ar.id
            ORDER BY overall_score DESC
            LIMIT 1
        )
        ORDER BY ar.created_at DESC
        """
    )
    history = []
    for row in rows:
        result = json.loads(str(row["result_json"])) if row.get("result_json") else {}
        history.append(
            {
                "analysis_id": row["id"],
                "job_title": row["title"] or "Untitled job",
                "created_at": row["created_at"],
                "resume_count": row["resume_count"],
                "cached_result_count": row["cached_result_count"],
                "recommended_resume": result.get("resume_name"),
                "overall_score": row["overall_score"],
            }
        )
    return history


def delete_history(analysis_id: int) -> bool:
    row: Optional[Dict[str, object]] = fetch_one("SELECT id FROM analysis_runs WHERE id = ?", (analysis_id,))
    if not row:
        return False
    execute_write("DELETE FROM analysis_runs WHERE id = ?", (analysis_id,))
    return True
