"""Dense job↔resume similarity (all-MiniLM-L6-v2), job vectors cached by the dedup content hash."""

import json
import logging
import os
import re
from datetime import datetime, timedelta

from deduplicator import _content_id, _get_expiry_days

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CACHE_FILE = ".embeddings_cache.json"
PROFILE_FILE = "applicant_profile.json"

logger = logging.getLogger(__name__)
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def job_text(job: dict) -> str:
    fields = ("title", "company", "location", "stipend", "salary", "description")
    parts = [str(job.get(f) or "").strip() for f in fields]
    return " | ".join(p for p in parts if p and p.lower() != "nan")


def load_resume_text() -> str:
    """RESUME_TEXT env (CI secret) first, then applicant_profile.json (local)."""
    text = os.environ.get("RESUME_TEXT", "").strip()
    if text:
        return text
    try:
        with open(PROFILE_FILE) as f:
            return str(json.load(f).get("resume_text", "")).strip()
    except (OSError, ValueError):
        return ""


def resume_chunks(text: str) -> list[str]:
    """Paragraph chunks: MiniLM truncates at 256 tokens, a whole resume doesn't fit.
    Drops the contact line (email/phone carry no signal)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [p for p in paras if not ("\n" not in p and "@" in p)] or paras


def _load_cache() -> dict:
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data.get("vectors", {}) if data.get("model") == MODEL_NAME else {}


def _save_cache(vectors: dict) -> None:
    cutoff = (datetime.utcnow() - timedelta(days=_get_expiry_days())).isoformat()
    kept = {k: v for k, v in vectors.items() if v["t"] >= cutoff}
    with open(CACHE_FILE, "w") as f:
        json.dump({"model": MODEL_NAME, "vectors": kept}, f)


def resume_similarity(jobs: list[dict]) -> list[float] | None:
    """Per job: max cosine over resume chunks. None if no resume or the model can't load."""
    resume = load_resume_text()
    if not resume:
        logger.warning("No RESUME_TEXT / resume_text — semantic ranking skipped.")
        return None
    try:
        import numpy as np
        model = _get_model()
    except Exception as e:
        logger.warning(f"Embedding model unavailable ({e}) — semantic ranking skipped.")
        return None

    resume_vecs = model.encode(resume_chunks(resume), normalize_embeddings=True)

    cache = _load_cache()
    keys = [_content_id(j) or "text:" + job_text(j) for j in jobs]
    missing = list({k: i for i, k in enumerate(keys) if k not in cache}.values())  # one per unique key
    if missing:
        now = datetime.utcnow().isoformat()
        vecs = model.encode([job_text(jobs[i]) for i in missing], normalize_embeddings=True)
        for i, v in zip(missing, vecs):
            cache[keys[i]] = {"t": now, "v": np.round(v, 5).tolist()}
    logger.info(f"Embeddings: {len(jobs) - len(missing)} cached, {len(missing)} computed")
    try:
        _save_cache(cache)
    except OSError as e:
        logger.warning(f"Could not save embedding cache: {e}")

    job_vecs = np.array([cache[k]["v"] for k in keys], dtype=np.float32)
    return (job_vecs @ resume_vecs.T).max(axis=1).tolist()
