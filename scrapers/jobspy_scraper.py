import logging
import time
from typing import Optional

from config_manager import load_config
from scrapers.base import JobDict

logger = logging.getLogger(__name__)

_SITE_MAP = {
    "linkedin":  "LinkedIn",
    "indeed":    "Indeed",
    "glassdoor": "Glassdoor",
}


def _format_compensation(min_amount: Optional[float], max_amount: Optional[float],
                          currency: str, interval: str) -> str:
    if not min_amount and not max_amount:
        return ""
    sym = "$" if currency in ("USD", "") else currency + " "
    interval_label = {"yearly": "/yr", "monthly": "/mo", "hourly": "/hr"}.get(str(interval).lower(), "")
    if min_amount and max_amount:
        return f"{sym}{min_amount:,.0f}–{sym}{max_amount:,.0f}{interval_label}"
    val = min_amount or max_amount
    return f"{sym}{val:,.0f}{interval_label}"


def _row_to_job(row, job_type: str) -> Optional[JobDict]:
    try:
        url = str(row.get("job_url") or "").strip()
        title = str(row.get("title") or "").strip()
        company = str(row.get("company") or "").strip()
        if not url or not title or not company:
            return None

        site = str(row.get("site") or "").lower()
        source = _SITE_MAP.get(site, site.title())

        parts = [
            str(row.get("city") or ""),
            str(row.get("state") or ""),
            str(row.get("country") or ""),
        ]
        location = ", ".join(p.strip() for p in parts if p.strip()) or str(row.get("location") or "Remote")

        min_amount = row.get("min_amount")
        max_amount = row.get("max_amount")
        currency   = str(row.get("currency") or "USD")
        interval   = str(row.get("interval") or "yearly")

        comp_str = _format_compensation(
            float(min_amount) if min_amount is not None else None,
            float(max_amount) if max_amount is not None else None,
            currency, interval,
        )

        date_posted = ""
        dp = row.get("date_posted")
        if dp is not None:
            try:
                date_posted = str(dp.date()) if hasattr(dp, "date") else str(dp)
            except Exception:
                date_posted = str(dp)

        is_remote_val = row.get("is_remote")
        is_remote = bool(is_remote_val) if is_remote_val is not None else None

        job: JobDict = {
            "title":       title,
            "company":     company,
            "location":    location,
            "url":         url,
            "source":      source,
            "job_type":    job_type,  # type: ignore[typeddict-item]
            "date_posted": date_posted,
            "is_remote":   is_remote,
            "currency":    currency,
        }
        if min_amount is not None:
            job["min_amount"] = float(min_amount)
        if max_amount is not None:
            job["max_amount"] = float(max_amount)
        if comp_str:
            if job_type == "internship":
                job["stipend"] = comp_str
            else:
                job["salary"] = comp_str

        return job
    except Exception as e:
        logger.debug(f"jobspy row conversion error: {e}")
        return None


def _scrape(keywords: list[str], job_type_param: str, is_remote: bool,
            results_wanted: int, hours_old: int, country_indeed: str,
            out_job_type: str) -> list[JobDict]:
    try:
        from jobspy import scrape_jobs  # type: ignore
    except ImportError:
        logger.error("python-jobspy not installed. Run: pip install python-jobspy")
        return []

    results: list[JobDict] = []
    seen_urls: set[str] = set()

    for keyword in keywords:
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=keyword,
                job_type=job_type_param,
                is_remote=is_remote,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country_indeed,
                linkedin_fetch_description=False,
                description_format="markdown",
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                job = _row_to_job(row, out_job_type)
                if job and job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    results.append(job)

            time.sleep(2)

        except Exception as e:
            logger.error(f"jobspy error for '{keyword}': {e}")
            continue

    logger.info(f"jobspy ({out_job_type}): {len(results)} raw results across {len(keywords)} keywords")
    return results


def scrape_jobspy_internships() -> list[JobDict]:
    cfg = load_config()["search"]
    return _scrape(
        keywords=cfg.get("jobspy_internship_keywords", []),
        job_type_param="internship",
        is_remote=False,
        results_wanted=cfg.get("jobspy_results_per_call", 15),
        hours_old=cfg.get("jobspy_hours_old", 26),
        country_indeed=cfg.get("jobspy_country_indeed", "worldwide"),
        out_job_type="internship",
    )


def scrape_jobspy_fulltime_remote() -> list[JobDict]:
    cfg = load_config()["search"]
    return _scrape(
        keywords=cfg.get("jobspy_fulltime_keywords", []),
        job_type_param="fulltime",
        is_remote=True,
        results_wanted=cfg.get("jobspy_results_per_call", 15),
        hours_old=cfg.get("jobspy_hours_old", 26),
        country_indeed=cfg.get("jobspy_country_indeed", "worldwide"),
        out_job_type="full_time_remote",
    )
