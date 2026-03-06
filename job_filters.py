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

SENIORITY_EXCLUDE_KEYWORDS = [
    "senior",
    "sr.",
    "lead",
    "principal",
    "staff engineer",
    "architect",
    "manager",
    "head of",
    "director",
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

INTERNSHIP_HINT_KEYWORDS = [
    "intern",
    "internship",
    "trainee",
    "apprentice",
    "graduate program",
]

DUBIOUS_TITLE_KEYWORDS = [
    "training",
    "course",
    "bootcamp",
    "mentor",
    "instructor",
    "coach",
    "referral",
    "commission",
]

DUBIOUS_COMPANY_KEYWORDS = [
    "staffing",
    "recruit",
    "consultancy",
    "outsourcing",
    "talent",
    "hr services",
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
    if any(word in role for word in SENIORITY_EXCLUDE_KEYWORDS):
        return False
    return any(word in role for word in TECH_INCLUDE_KEYWORDS)


def _is_internship_like(job: dict) -> bool:
    title = _normalize(str(job.get("title", "")))
    url = _normalize(str(job.get("url", "")))
    text = f"{title} {url}"
    return any(token in text for token in INTERNSHIP_HINT_KEYWORDS)


def _looks_dubious(job: dict) -> bool:
    title = _normalize(str(job.get("title", "")))
    company = _normalize(str(job.get("company", "")))
    if any(token in title for token in DUBIOUS_TITLE_KEYWORDS):
        return True
    if any(token in company for token in DUBIOUS_COMPANY_KEYWORDS):
        return True
    return False


def quality_score(job: dict) -> int:
    title = _normalize(str(job.get("title", "")))
    location = _normalize(str(job.get("location", "")))
    stipend = _normalize(str(job.get("stipend", "")))

    score = 0
    if _is_internship_like(job):
        score += 4
    if any(token in title for token in ["software engineer", "sde", "developer", "devops", "machine learning", "ai", "data engineer"]):
        score += 3
    if any(token in location for token in ["remote", "hybrid", "india", "united states", "europe"]):
        score += 1
    if stipend:
        score += 1
    if _looks_dubious(job):
        score -= 5
    return score


def _extract_amounts(stipend_text: str) -> list[int]:
    values = re.findall(r"\d[\d,]*", stipend_text or "")
    amounts = []
    for value in values:
        num = value.replace(",", "")
        if num.isdigit():
            amounts.append(int(num))
    return amounts


def _passes_min_stipend(stipend_text: str, minimum_inr: int) -> bool:
    if minimum_inr <= 0:
        return True
    stipend = _normalize(stipend_text)
    amounts = _extract_amounts(stipend_text)
    if not amounts:
        return False

    # For INR-looking stipends, enforce minimum; for other currencies keep if paid.
    looks_inr = any(token in stipend for token in ["₹", "rs", "inr"]) or "$" not in stipend
    if looks_inr:
        return max(amounts) >= minimum_inr
    return True


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
    min_stipend_inr = int(os.environ.get("MIN_STIPEND_INR", "5000"))
    source = str(job.get("source", "")).strip().lower()

    stipend = str(job.get("stipend", "")).strip()
    if stipend:
        if not _is_paid_text(stipend):
            return False
        return _passes_min_stipend(stipend, min_stipend_inr)

    paid_flag = job.get("paid")
    if isinstance(paid_flag, bool):
        return paid_flag

    # LinkedIn listings usually do not expose stipend in search results.
    # Keep them when strict mode is on, and let title relevance filters do the cleanup.
    if source == "linkedin":
        return True

    # If strict mode is enabled, unknown stipend is dropped.
    return not strict_paid_only


def filter_relevant_jobs(jobs: list[dict]) -> list[dict]:
    linkedin_min_quality = int(os.environ.get("LINKEDIN_MIN_QUALITY", "6"))
    require_linkedin_intern = os.environ.get("LINKEDIN_REQUIRE_INTERNSHIP_HINT", "true").lower() == "true"

    filtered = []
    for job in jobs:
        source = str(job.get("source", "")).strip().lower()
        title = str(job.get("title", ""))

        if not is_tech_role(title):
            continue
        if _looks_dubious(job):
            continue

        if source == "linkedin" and require_linkedin_intern and not _is_internship_like(job):
            continue

        if not is_paid_internship(job):
            continue

        if source == "linkedin" and quality_score(job) < linkedin_min_quality:
            continue

        filtered.append(job)
    return filtered
