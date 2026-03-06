import os
import re


TECH_INCLUDE_KEYWORDS = [
    "software engineer",
    "software developer",
    "sde",
    "soe",
    "full stack",
    "frontend",
    "front end",
    "backend",
    "back end",
    "web developer",
    "app developer",
    "mobile developer",
    "android",
    "ios",
    "devops",
    "site reliability",
    "sre",
    "platform engineer",
    "machine learning",
    "ml",
    "ai",
    "artificial intelligence",
    "data science",
    "data engineer",
    "qa engineer",
    "test engineer",
    "software testing",
]

TECH_EXCLUDE_KEYWORDS = [
    "business",
    "fundraising",
    "content writer",
    "marketing",
    "sales",
    "talent acquisition",
    "human resources",
    "hr",
    "operations",
    "coordination",
    "charity",
    "secretary",
    "travel host",
    "audit agent",
    "subject matter expert",
    "sme",
    "social sector",
    "accounting",
    "logistics",
]

PAID_BLOCKLIST = [
    "unpaid",
    "without stipend",
    "no stipend",
    "volunteer",
    "incentive based",
    "performance based",
    "commission only",
    "0/month",
    "0 per month",
]


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_tech_role(title: str) -> bool:
    role = _normalize(title)
    if not role:
        return False
    if any(word in role for word in TECH_EXCLUDE_KEYWORDS):
        return False
    return any(word in role for word in TECH_INCLUDE_KEYWORDS)


def _is_paid_text(stipend_text: str) -> bool:
    stipend = _normalize(stipend_text)
    if not stipend:
        return False
    if any(token in stipend for token in PAID_BLOCKLIST):
        return False
    # Accept explicit monetary formats.
    if any(sym in stipend for sym in ["₹", "rs", "inr", "$", "eur", "gbp"]):
        return True
    return bool(re.search(r"\b\d{3,}\b", stipend))


def is_paid_internship(job: dict) -> bool:
    strict_paid_only = os.environ.get("STRICT_PAID_ONLY", "true").lower() == "true"

    stipend = str(job.get("stipend", "")).strip()
    if stipend:
        return _is_paid_text(stipend)

    paid_flag = job.get("paid")
    if isinstance(paid_flag, bool):
        return paid_flag

    # If strict mode is enabled, unknown stipend is dropped.
    return not strict_paid_only


def filter_relevant_jobs(jobs: list[dict]) -> list[dict]:
    filtered = []
    for job in jobs:
        title = str(job.get("title", ""))
        if not is_tech_role(title):
            continue
        if not is_paid_internship(job):
            continue
        filtered.append(job)
    return filtered
