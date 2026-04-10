import json
import os
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qs
from datetime import datetime, timedelta

SEEN_JOBS_FILE = "seen_jobs.json"


def _get_expiry_days() -> int:
    try:
        from config_manager import load_config
        return int(load_config()["dedup"]["expiry_days"])
    except Exception:
        return 60


def _normalize_url(url: str) -> str:
    """Strip tracking/session query params so the same job with different params deduplicates."""
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
        # Drop all query params for LinkedIn and Internshala — job ID is in the path
        if any(host in parsed.netloc for host in ["linkedin.com", "internshala.com"]):
            normalized = parsed._replace(query="", fragment="")
        else:
            # For other sources, strip known tracking params only
            keep_params = {k: v for k, v in parse_qs(parsed.query).items()
                          if k not in {"refId", "trackingId", "trk", "utm_source",
                                       "utm_medium", "utm_campaign", "sessionId"}}
            query = "&".join(f"{k}={v[0]}" for k, v in keep_params.items())
            normalized = parsed._replace(query=query, fragment="")

        # Normalize scheme and www prefix
        netloc = normalized.netloc.lower().removeprefix("www.")
        path = normalized.path.rstrip("/") or "/"
        normalized = normalized._replace(scheme="https", netloc=netloc, path=path)
        return urlunparse(normalized)
    except Exception:
        return url


def _url_id(job: dict) -> str:
    url = _normalize_url(job.get("url", ""))
    key = url or f"{job.get('title','').strip().lower()}|{job.get('company','').strip().lower()}"
    return hashlib.md5(key.encode()).hexdigest()


def _content_id(job: dict) -> str:
    """Secondary hash on title+company to catch cross-source duplicates."""
    title = job.get("title", "").strip().lower()
    company = job.get("company", "").strip().lower()
    if not title and not company:
        return ""
    return "content:" + hashlib.md5(f"{title}|{company}".encode()).hexdigest()


def load_seen() -> dict:
    if not os.path.exists(SEEN_JOBS_FILE):
        return {}
    with open(SEEN_JOBS_FILE, "r") as f:
        return json.load(f)


def save_seen(seen: dict):
    expiry_days = _get_expiry_days()
    cutoff = (datetime.utcnow() - timedelta(days=expiry_days)).isoformat()
    pruned = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(pruned, f, indent=2)


def filter_new_jobs(jobs: list[dict]) -> list[dict]:
    seen = load_seen()
    new_jobs = []
    now = datetime.utcnow().isoformat()

    for job in jobs:
        uid = _url_id(job)
        cid = _content_id(job)

        if uid in seen or (cid and cid in seen):
            continue

        seen[uid] = now
        if cid:
            seen[cid] = now
        new_jobs.append(job)

    save_seen(seen)
    return new_jobs
