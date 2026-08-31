from __future__ import annotations

import json
from typing import Any, Dict

from .database import execute_write, fetch_all, fetch_one, utc_now_iso
from .matching import MATCH_WEIGHTS, matching_config_hash

DEFAULT_SETTINGS = {
    "theme": "system",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "mistral:latest",
    "matching_weights": MATCH_WEIGHTS,
    "embedding_model": "local-hashing-embedding-v1",
}


def validate_weights(weights: Dict[str, float]) -> Dict[str, float]:
    expected = set(MATCH_WEIGHTS)
    if set(weights) != expected:
        raise ValueError("Matching weights must include every scoring category.")
    total = sum(float(value) for value in weights.values())
    if round(total, 4) != 1.0:
        raise ValueError("Matching weights must equal 100%.")
    return {key: float(weights[key]) for key in MATCH_WEIGHTS}


def get_settings_payload() -> Dict[str, Any]:
    rows = fetch_all("SELECT key, value FROM app_settings")
    payload = dict(DEFAULT_SETTINGS)
    for row in rows:
        payload[str(row["key"])] = json.loads(str(row["value"]))
    payload["matching_config_hash"] = matching_config_hash(payload["matching_weights"])
    return payload


def update_settings_payload(updates: Dict[str, Any]) -> Dict[str, Any]:
    allowed = set(DEFAULT_SETTINGS)
    timestamp = utc_now_iso()
    for key, value in updates.items():
        if key not in allowed:
            raise ValueError(f"Unknown setting: {key}")
        if key == "matching_weights":
            value = validate_weights(value)
        if key == "theme" and value not in {"light", "dark", "system"}:
            raise ValueError("Theme must be light, dark, or system.")
        execute_write(
            """
            INSERT INTO app_settings(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, json.dumps(value), timestamp),
        )
    return get_settings_payload()


def get_setting(key: str) -> Any:
    row = fetch_one("SELECT value FROM app_settings WHERE key = ?", (key,))
    if not row:
        return DEFAULT_SETTINGS[key]
    return json.loads(str(row["value"]))
