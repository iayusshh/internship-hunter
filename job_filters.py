import os
import re

from config_manager import load_config


def _cfg() -> dict:
    return load_config()["filters"]


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    return re.sub(r"\s+", " ", text)


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
    text = _normalize(f"{job.get('title', '')} {job.get('url', '')}")
    hints = cfg.get("internship_hint_keywords", ["intern", "internship", "trainee", "apprentice", "graduate program"])
    return any(token in text for token in hints)


def _is_not_internship(job: dict) -> bool:
    """For full-time roles: confirm the title is NOT an internship listing."""
    title = _normalize(str(job.get("title", "")))
    return not any(t in title for t in ("intern", "trainee", "apprentice"))


def _looks_dubious(job: dict) -> bool:
    cfg = _cfg()
    title   = _normalize(str(job.get("title", "")))
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
    return any(token in company for token in cfg["blocked_companies"])


def _likely_us_only_role(job: dict) -> bool:
    cfg = _cfg()
    text = _normalize(" ".join([
        str(job.get("title", "")),
        str(job.get("company", "")),
        str(job.get("location", "")),
        str(job.get("url", "")),
    ]))
    has_us_hint     = any(token in text for token in cfg["us_only_hints"])
    has_global_hint = any(token in text for token in cfg["global_friendly_hints"])
    return has_us_hint and not has_global_hint


def _has_remote_hint(job: dict) -> bool:
    """Check if a full-time job is remote (by flag or location text)."""
    if job.get("is_remote") is True:
        return True
    location = _normalize(str(job.get("location", "")))
    return "remote" in location or "anywhere" in location or "worldwide" in location


def quality_score(job: dict) -> int:
    job_type = str(job.get("job_type", "internship"))
    title    = _normalize(str(job.get("title", "")))
    location = _normalize(str(job.get("location", "")))

    score = 0
    if _looks_dubious(job):
        return score - 5

    strong_tech = ["software engineer", "sde", "developer", "devops", "machine learning", "ai", "data engineer"]

    if job_type == "internship":
        if _is_internship_like(job):
            score += 4
        if any(token in title for token in strong_tech):
            score += 3
        if any(token in location for token in ["remote", "hybrid", "india", "united states", "europe"]):
            score += 1
        if job.get("stipend"):
            score += 1

    else:  # full_time_remote
        if job.get("is_remote") is True or "remote" in location:
            score += 3
        if any(token in title for token in strong_tech):
            score += 3
        if job.get("salary") or job.get("min_amount"):
            score += 2

    return score


# ── Paid / compensation checks ────────────────────────────────────────────────

def _extract_amounts(text: str) -> list[int]:
    values = re.findall(r"\d[\d,]*", text or "")
    return [int(v.replace(",", "")) for v in values if v.replace(",", "").isdigit()]


def _passes_min_stipend(stipend_text: str, minimum_inr: int) -> bool:
    if minimum_inr <= 0:
        return True
    stipend = _normalize(stipend_text)
    amounts = _extract_amounts(stipend_text)
    if not amounts:
        return False
    looks_inr = any(t in stipend for t in ["₹", "rs", "inr"]) or "$" not in stipend
    if looks_inr:
        return max(amounts) >= minimum_inr
    return True


def _is_paid_text(text: str) -> bool:
    cfg = _cfg()
    norm = _normalize(text)
    if not norm:
        return False
    # Use word-boundary regex so "0/month" doesn't match inside "15000/month"
    for token in cfg["paid_blocklist"]:
        if re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", norm):
            return False
    if any(sym in norm for sym in ["₹", "rs", "inr", "$", "eur", "gbp"]):
        return True
    return bool(re.search(r"\b\d{3,}\b", norm))


def is_paid_internship(job: dict) -> bool:
    cfg  = _cfg()
    env  = os.environ
    strict = env.get("STRICT_PAID_ONLY", str(cfg.get("strict_paid_only", True))).lower() in ("true", "1", "yes")
    min_inr = int(env.get("MIN_STIPEND_INR", str(cfg.get("min_stipend_inr", 5000))))
    source = str(job.get("source", "")).strip().lower()

    stipend = str(job.get("stipend", "")).strip()
    if stipend:
        if not _is_paid_text(stipend):
            return False
        return _passes_min_stipend(stipend, min_inr)

    paid_flag = job.get("paid")
    if isinstance(paid_flag, bool):
        return paid_flag

    # jobspy/LinkedIn results don't expose stipend in search — assume paid
    if source in ("linkedin", "indeed", "glassdoor", "yc jobs", "wellfound"):
        return True

    return not strict


def _passes_min_salary(job: dict) -> bool:
    """For full-time remote: check numeric salary against configured minimum."""
    cfg = _cfg()
    min_usd = int(cfg.get("min_salary_usd_annual", 40000))
    if min_usd <= 0:
        return True

    min_amount = job.get("min_amount")
    if min_amount is not None:
        try:
            return float(min_amount) >= min_usd
        except (TypeError, ValueError):
            pass

    # If no numeric amount, don't reject — salary may not be disclosed
    return True


# ── Main filter entry point ───────────────────────────────────────────────────

def filter_relevant_jobs(jobs: list[dict]) -> list[dict]:
    cfg = _cfg()
    env = os.environ

    enable_internships   = cfg.get("enable_internships", True)
    enable_fulltime      = cfg.get("enable_full_time_remote", True)
    require_remote_hint  = cfg.get("full_time_require_remote_hint", True)
    fulltime_min_quality = int(cfg.get("full_time_min_quality", 4))
    linkedin_min_quality = int(env.get("LINKEDIN_MIN_QUALITY", str(cfg.get("linkedin_min_quality", 6))))
    require_intern_hint  = env.get(
        "LINKEDIN_REQUIRE_INTERNSHIP_HINT",
        str(cfg.get("linkedin_require_internship_hint", True))
    ).lower() in ("true", "1", "yes")
    exclude_us_only = env.get(
        "EXCLUDE_US_ONLY_ROLES",
        str(cfg.get("exclude_us_only", True))
    ).lower() in ("true", "1", "yes")

    filtered = []
    for job in jobs:
        jtype  = str(job.get("job_type", "internship"))
        source = str(job.get("source", "")).strip().lower()
        title  = str(job.get("title", ""))

        # Skip if job type is disabled
        if jtype == "internship" and not enable_internships:
            continue
        if jtype == "full_time_remote" and not enable_fulltime:
            continue

        # Universal checks
        if _is_blocked_company(job):
            continue
        if not is_tech_role(title):
            continue
        if _looks_dubious(job):
            continue

        if jtype == "internship":
            if exclude_us_only and _likely_us_only_role(job):
                continue

            # jobspy-sourced LinkedIn/Indeed/Glassdoor internships: require intern hint
            if source in ("linkedin", "indeed", "glassdoor") and require_intern_hint:
                if not _is_internship_like(job):
                    continue

            if not is_paid_internship(job):
                continue

            if source in ("linkedin", "indeed", "glassdoor") and quality_score(job) < linkedin_min_quality:
                continue

        elif jtype == "full_time_remote":
            if not _is_not_internship(job):
                continue

            if require_remote_hint and not _has_remote_hint(job):
                continue

            if not _passes_min_salary(job):
                continue

            if quality_score(job) < fulltime_min_quality:
                continue

        filtered.append(job)

    return filtered
