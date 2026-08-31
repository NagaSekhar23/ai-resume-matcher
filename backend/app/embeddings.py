from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from typing import Iterable, List, Optional

import numpy as np

from .config import get_settings
from .text_processing import normalize_text

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
FALLBACK_EMBEDDING_MODEL = "local-hashing-embedding-v1"


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def serialize_embedding(vector: np.ndarray) -> bytes:
    return json.dumps([float(value) for value in vector.tolist()]).encode("utf-8")


def deserialize_embedding(blob: bytes) -> np.ndarray:
    return np.array(json.loads(blob.decode("utf-8")), dtype=np.float32)


@lru_cache(maxsize=1)
def _load_sentence_transformer() -> Optional[object]:
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    except Exception:
        return None


def _hash_embedding(text: str, dimensions: int = 384) -> np.ndarray:
    vector = np.zeros(dimensions, dtype=np.float32)
    tokens = normalize_text(text).split()
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(float(np.dot(vector, vector)))
    if norm:
        vector = vector / norm
    return vector


def embedding_model_name() -> str:
    if get_settings().use_sentence_transformers and _load_sentence_transformer() is not None:
        return DEFAULT_EMBEDDING_MODEL
    return FALLBACK_EMBEDDING_MODEL


def embed_texts(texts: Iterable[str]) -> List[np.ndarray]:
    text_list = list(texts)
    model = _load_sentence_transformer() if get_settings().use_sentence_transformers else None
    if model is not None:
        vectors = model.encode(text_list, normalize_embeddings=True)
        return [np.array(vector, dtype=np.float32) for vector in vectors]
    return [_hash_embedding(text) for text in text_list]
