from __future__ import annotations

import hashlib
from pathlib import Path

from .config import get_settings


def sha256_digest(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def stored_filename(file_hash: str, extension: str) -> str:
    return f"{file_hash}{extension}"


def save_upload(file_bytes: bytes, filename: str) -> Path:
    upload_dir = get_settings().upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / filename
    path.write_bytes(file_bytes)
    return path


def delete_upload(filename: str) -> None:
    path = get_settings().upload_dir / filename
    try:
        path.unlink()
    except FileNotFoundError:
        return
