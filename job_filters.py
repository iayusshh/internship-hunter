import os
import re

from config_manager import load_config


def _cfg() -> dict:
    return load_config()["filters"]


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_tech_role(title: str) -> bool:
    cfg = _cfg()
    role = _normalize(title)
    if not role:
        return False
    if any(word in role for word in cfg["tech_exclude_keywords"]):
        return False
    if any(word in role for word in cfg["seniority_exclude_keywords"]):
        return False
    return any(word in role for word in cfg["tech_include_keywords"])


def _is_internship_like(job: dict) -> bool:
    cfg = _cfg()
    title = _normalize(str(job.get("title", "")))
    url = _normalize(str(job.get("url", "")))
    text = f"{title} {url}"
    return any(token in text for token in cfg.get("internship_hint_keywords", [
        "intern", "internship", "trainee", "apprentice", "graduate program"
    ]))


def _looks_dubious(job: dict) -> bool:
    cfg = _cfg()
    title = _normalize(str(job.get("title", "")))
    company = _normalize(str(job.get("company", "")))
    if any(token in title for token in cfg["dubious_title_keywords"]):
        return True
    if any(token in company for token in cfg["dubious_company_keywords"]):
        return True
    return False


def _is_blocked_company(job: dict) -> bool:
    cfg = _cfg()
    company = _normalize(str(job.get("company", "")))
    if not company:
        return False
    blocked = set(cfg["blocked_companies"])
    return any(token in company for token in blocked)


def _likely_us_only_role(job: dict) -> bool:
    cfg = _cfg()
    text = _normalize(
        " ".join([
            str(job.get("title", "")),
            str(job.get("company", "")),
            str(job.get("location", "")),
            str(job.get("url", "")),
        ])
    )
    has_us_hint = any(token in text for token in cfg["us_only_hints"])
    has_global_hint = any(token in text for token in cfg["global_friendly_hints"])
    return has_us_hint and not has_global_hint


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

    looks_inr = any(token in stipend for token in ["₹", "rs", "inr"]) or "$" not in stipend
    if looks_inr:
        return max(amounts) >= minimum_inr
    return True


def _is_paid_text(stipend_text: str) -> bool:
    cfg = _cfg()
    stipend = _normalize(stipend_text)
    if not stipend:
        return False
    if any(token in stipend for token in cfg["paid_blocklist"]):
        return False
    if any(sym in stipend for sym in ["₹", "rs", "inr", "$", "eur", "gbp"]):
        return True
    return bool(re.search(r"\b\d{3,}\b", stipend))


def is_paid_internship(job: dict) -> bool:
    cfg = _cfg()
    strict_paid_only = os.environ.get("STRICT_PAID_ONLY", str(cfg.get("strict_paid_only", True))).lower() in ("true", "1", "yes")
    min_stipend_inr = int(os.environ.get("MIN_STIPEND_INR", str(cfg.get("min_stipend_inr", 5000))))
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
    if source == "linkedin":
        return True

    return not strict_paid_only


def filter_relevant_jobs(jobs: list[dict]) -> list[dict]:
    cfg = _cfg()
    linkedin_min_quality = int(os.environ.get("LINKEDIN_MIN_QUALITY", str(cfg.get("linkedin_min_quality", 6))))
    require_linkedin_intern = os.environ.get(
        "LINKEDIN_REQUIRE_INTERNSHIP_HINT",
        str(cfg.get("linkedin_require_internship_hint", True))
    ).lower() in ("true", "1", "yes")
    exclude_us_only_roles = os.environ.get(
        "EXCLUDE_US_ONLY_ROLES",
        str(cfg.get("exclude_us_only", True))
    ).lower() in ("true", "1", "yes")

    filtered = []
    for job in jobs:
        source = str(job.get("source", "")).strip().lower()
        title = str(job.get("title", ""))

        if _is_blocked_company(job):
            continue
        if not is_tech_role(title):
            continue
        if _looks_dubious(job):
            continue

        if exclude_us_only_roles and _likely_us_only_role(job):
            continue

        if source == "linkedin" and require_linkedin_intern and not _is_internship_like(job):
            continue

        if not is_paid_internship(job):
            continue

        if source == "linkedin" and quality_score(job) < linkedin_min_quality:
            continue

        filtered.append(job)
    return filtered
