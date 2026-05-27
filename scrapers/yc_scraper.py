"""
YC Jobs scraper — targets workatastartup.com (official YC job board).
Parses the __NEXT_DATA__ JSON blob embedded in the page HTML.
"""

import json
import logging
import time

import requests
from bs4 import BeautifulSoup

from config_manager import load_config
from scrapers.base import JobDict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_SCRAPE_URLS = [
    "https://www.workatastartup.com/jobs?jobType=eng&remote=yes",
    "https://www.workatastartup.com/jobs?jobType=eng&remote=yes&internship=yes",
]


def _classify_job_type(listing: dict) -> str:
    raw = str(listing.get("type") or listing.get("job_type") or "").lower()
    if "intern" in raw:
        return "internship"
    return "full_time_remote"


def _parse_jobs_from_next_data(data: dict) -> list[dict]:
    """Extract raw job listings from Next.js __NEXT_DATA__ blob."""
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        # Listings may be under companies[].jobs[] or jobs[] depending on page type
        jobs_flat = page_props.get("jobs", [])
        if jobs_flat:
            return jobs_flat

        companies = page_props.get("companies", [])
        result = []
        for company in companies:
            for job in company.get("jobs", []):
                job.setdefault("_company_name", company.get("name", ""))
                job.setdefault("_company_slug", company.get("slug", ""))
                result.append(job)
        return result
    except Exception:
        return []


def scrape_yc() -> list[JobDict]:
    results: list[JobDict] = []
    seen_ids: set[str] = set()

    for page_url in _SCRAPE_URLS:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            next_data_tag = soup.find("script", id="__NEXT_DATA__")
            if not next_data_tag or not next_data_tag.string:
                logger.warning(f"YC: __NEXT_DATA__ not found on {page_url}")
                continue

            data = json.loads(next_data_tag.string)
            raw_jobs = _parse_jobs_from_next_data(data)

            for item in raw_jobs:
                try:
                    job_id = str(item.get("id") or item.get("slug") or "")
                    if job_id and job_id in seen_ids:
                        continue
                    if job_id:
                        seen_ids.add(job_id)

                    title   = str(item.get("title") or item.get("name") or "").strip()
                    company = str(
                        item.get("company", {}).get("name")
                        or item.get("_company_name")
                        or item.get("company_name")
                        or ""
                    ).strip()
                    location = str(item.get("location") or item.get("remote_ok") or "Remote").strip()
                    if isinstance(location, bool) or location.lower() in ("true", "false", "1", "0"):
                        location = "Remote"

                    slug = item.get("_company_slug") or item.get("company", {}).get("slug") or ""
                    job_slug = item.get("slug") or job_id
                    if slug and job_slug:
                        url = f"https://www.workatastartup.com/companies/{slug}/jobs/{job_slug}"
                    elif job_id:
                        url = f"https://www.workatastartup.com/jobs/{job_id}"
                    else:
                        url = "https://www.workatastartup.com/jobs"

                    if not title or not company:
                        continue

                    job_type = _classify_job_type(item)
                    compensation = str(item.get("compensation") or item.get("salary") or "").strip()

                    job = JobDict(
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        source="YC Jobs",
                        job_type=job_type,  # type: ignore[typeddict-item]
                        date_posted="Recent",
                        is_remote=True,
                    )
                    if compensation:
                        if job_type == "internship":
                            job["stipend"] = compensation
                        else:
                            job["salary"] = compensation

                    results.append(job)

                except Exception as e:
                    logger.debug(f"YC item parse error: {e}")

            time.sleep(1.5)

        except Exception as e:
            logger.error(f"YC scraper error for {page_url}: {e}")

    logger.info(f"YC Jobs: {len(results)} results")
    return results
