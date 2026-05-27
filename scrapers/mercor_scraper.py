"""
Mercor jobs scraper.
Hits the public REST API at aws.api.mercor.com — no auth required, just
the Origin/Referer headers. Returns all remote listings; tech-relevance
filtering is handled downstream by filter_relevant_jobs().
"""

import logging
import re
import time

import requests

from scrapers.base import JobDict

logger = logging.getLogger(__name__)

_API_URL = "https://aws.api.mercor.com/work/listings-explore-page"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://work.mercor.com",
    "Referer": "https://work.mercor.com/explore",
}


def _fmt_salary(min_r, max_r, freq: str) -> str:
    if not min_r and not max_r:
        return ""
    unit = {"hourly": "/hr", "monthly": "/mo", "yearly": "/yr", "annual": "/yr"}.get(
        (freq or "").lower(), f"/{freq}" if freq else ""
    )
    if min_r and max_r and min_r != max_r:
        return f"${min_r:.0f}–${max_r:.0f} {unit}".strip()
    val = min_r or max_r
    return f"${val:.0f} {unit}".strip()


def scrape_mercor() -> list[JobDict]:
    try:
        resp = requests.get(_API_URL, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        listings = resp.json().get("listings", [])
    except Exception as e:
        logger.error(f"Mercor: API request failed: {e}")
        return []

    results: list[JobDict] = []
    seen_ids: set[str] = set()

    for item in listings:
        try:
            if item.get("status") != "active":
                continue

            listing_id = str(item.get("listingId") or "")
            if not listing_id or listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)

            title = str(item.get("title") or "").strip()
            company = str(
                item.get("companyName") or item.get("companyAlias") or "Mercor Client"
            ).strip()
            if not title:
                continue

            location = str(item.get("location") or "Remote").strip() or "Remote"
            if item.get("workArrangement", "").lower() == "remote":
                location = location if location != "Remote" else "Remote"

            salary_raw = _fmt_salary(
                item.get("rateMin"), item.get("rateMax"), item.get("payRateFrequency", "")
            )
            url = f"https://work.mercor.com/listing/{listing_id}"
            date_posted = str(item.get("postedAt") or item.get("createdAt") or "Recent")

            job = JobDict(
                title=title,
                company=company,
                location=location,
                url=url,
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

    logger.info(f"Mercor: {len(results)} listings fetched")
    return results
