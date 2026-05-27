"""
Mercor jobs scraper.
Hits the public JSON REST API at work.mercor.com/api/jobs/.
All results are full_time_remote.
"""

import logging
import time

import requests

from config_manager import load_config
from scrapers.base import JobDict

logger = logging.getLogger(__name__)

_BASE_URL = "https://work.mercor.com/api/jobs/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://work.mercor.com/jobs/",
}


def scrape_mercor() -> list[JobDict]:
    keywords = load_config()["search"].get("mercor_keywords", [])
    results: list[JobDict] = []
    seen_ids: set[str] = set()

    for keyword in keywords:
        try:
            resp = requests.get(
                _BASE_URL,
                headers=HEADERS,
                params={
                    "search": keyword,
                    "employment_type": "full_time",
                    "page": 1,
                },
                timeout=15,
            )

            if resp.status_code == 404:
                logger.warning(f"Mercor: API endpoint returned 404 — skipping '{keyword}'")
                continue

            resp.raise_for_status()
            data = resp.json()

            # Handle both paginated {"results": [...]} and plain list responses
            items = data if isinstance(data, list) else data.get("results", data.get("jobs", []))

            for item in items:
                try:
                    job_id = str(item.get("id") or "")
                    if job_id and job_id in seen_ids:
                        continue
                    if job_id:
                        seen_ids.add(job_id)

                    title   = str(item.get("title") or item.get("job_title") or "").strip()
                    company = str(item.get("company_name") or item.get("company") or "").strip()
                    if not title or not company:
                        continue

                    location = str(item.get("location") or "Remote").strip()
                    apply_link = str(item.get("apply_link") or item.get("url") or "").strip()
                    if not apply_link and job_id:
                        apply_link = f"https://work.mercor.com/jobs/{job_id}"

                    salary_raw = str(item.get("salary") or item.get("compensation") or "").strip()
                    date_posted = str(item.get("created_at") or item.get("posted_at") or "Recent")

                    job = JobDict(
                        title=title,
                        company=company,
                        location=location,
                        url=apply_link,
                        source="Mercor",
                        job_type="full_time_remote",
                        date_posted=date_posted,
                        is_remote=True,
                    )
                    if salary_raw:
                        job["salary"] = salary_raw

                    results.append(job)

                except Exception as e:
                    logger.debug(f"Mercor item parse error: {e}")

            time.sleep(1.0)

        except requests.HTTPError as e:
            logger.error(f"Mercor HTTP error for '{keyword}': {e}")
        except Exception as e:
            logger.error(f"Mercor error for '{keyword}': {e}")

    logger.info(f"Mercor: {len(results)} results")
    return results
