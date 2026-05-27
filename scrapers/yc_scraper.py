"""
YC Jobs scraper — targets workatastartup.com (official YC job board).
The site uses Inertia.js; job data lives in the `data-page` attribute of
the first <div data-page=...> element, HTML-escaped JSON.
"""

import html
import json
import logging
import time

import requests
from bs4 import BeautifulSoup

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
    raw = str(listing.get("jobType") or "").lower()
    if "intern" in raw:
        return "internship"
    return "full_time_remote"


def scrape_yc() -> list[JobDict]:
    results: list[JobDict] = []
    seen_ids: set[str] = set()

    for page_url in _SCRAPE_URLS:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            page_div = soup.find("div", attrs={"data-page": True})
            if not page_div:
                logger.warning(f"YC: data-page element not found on {page_url}")
                continue

            data = json.loads(html.unescape(page_div["data-page"]))
            raw_jobs = data.get("props", {}).get("jobs", [])

            for item in raw_jobs:
                try:
                    job_id = str(item.get("id") or "")
                    if job_id and job_id in seen_ids:
                        continue
                    if job_id:
                        seen_ids.add(job_id)

                    title   = str(item.get("title") or "").strip()
                    company = str(item.get("companyName") or "").strip()
                    if not title or not company:
                        continue

                    location    = str(item.get("location") or "Remote").strip()
                    salary_raw  = str(item.get("salary") or "").strip()
                    job_type    = _classify_job_type(item)
                    company_slug = str(item.get("companySlug") or "")
                    url = (
                        f"https://www.workatastartup.com/jobs/{job_id}"
                        if job_id else "https://www.workatastartup.com/jobs"
                    )

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
                    if salary_raw:
                        if job_type == "internship":
                            job["stipend"] = salary_raw
                        else:
                            job["salary"] = salary_raw

                    results.append(job)

                except Exception as e:
                    logger.debug(f"YC item parse error: {e}")

            time.sleep(1.5)

        except Exception as e:
            logger.error(f"YC scraper error for {page_url}: {e}")

    logger.info(f"YC Jobs: {len(results)} results")
    return results
