import json
import os
import hashlib
from datetime import datetime, timedelta

SEEN_JOBS_FILE = "seen_jobs.json"
EXPIRY_DAYS = 30  # forget jobs older than 30 days to keep file lean


def _job_id(job: dict) -> str:
    """Generate a stable unique ID for a job based on URL or title+company."""
    key = job.get("url") or f"{job.get('title','')}|{job.get('company','')}"
    return hashlib.md5(key.strip().lower().encode()).hexdigest()


def load_seen() -> dict:
    if not os.path.exists(SEEN_JOBS_FILE):
        return {}
    with open(SEEN_JOBS_FILE, "r") as f:
        return json.load(f)


def save_seen(seen: dict):
    # Prune entries older than EXPIRY_DAYS
    cutoff = (datetime.utcnow() - timedelta(days=EXPIRY_DAYS)).isoformat()
    pruned = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(pruned, f, indent=2)


def filter_new_jobs(jobs: list[dict]) -> list[dict]:
    seen = load_seen()
    new_jobs = []
    now = datetime.utcnow().isoformat()

    for job in jobs:
        jid = _job_id(job)
        if jid not in seen:
            seen[jid] = now
            new_jobs.append(job)

    save_seen(seen)
    return new_jobs
