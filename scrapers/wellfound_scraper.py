"""
Wellfound (formerly AngelList) scraper.
Parses the __APOLLO_STATE__ JSON blob embedded in search result pages.
Gracefully returns [] if DataDome bot-protection blocks the request.
"""

import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from config_manager import load_config
from scrapers.base import JobDict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _classify_job_type(listing: dict) -> str:
    raw = str(listing.get("jobType") or listing.get("job_type") or "").lower()
    if "intern" in raw:
        return "internship"
    return "full_time_remote"


def _extract_company_name(apollo: dict, listing: dict) -> str:
    company_ref = listing.get("startupListing") or listing.get("company")
    if isinstance(company_ref, dict):
        ref_id = company_ref.get("__ref") or company_ref.get("id")
        if ref_id and ref_id in apollo:
            return str(apollo[ref_id].get("name") or "").strip()
        return str(company_ref.get("name") or "").strip()
    return ""


def _scrape_role(role: str) -> list[JobDict]:
    url = f"https://wellfound.com/role/r/{role}?remote=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)

        # DataDome protection check
        if resp.status_code in (403, 429) or "datadome" in resp.text.lower():
            logger.warning(f"Wellfound: bot-protection triggered for '{role}' — skipping")
            return []

        resp.raise_for_status()

        match = re.search(
            r'<script[^>]+id=["\']__APOLLO_STATE__["\'][^>]*>(.*?)</script>',
            resp.text, re.S,
        )
        if not match:
            # Fallback: try finding it in any script tag
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup.find_all("script"):
                if tag.string and "JobListing:" in tag.string:
                    match = re.search(r'({.*})', tag.string, re.S)
                    break

        if not match:
            logger.warning(f"Wellfound: __APOLLO_STATE__ not found for role '{role}'")
            return []

        apollo = json.loads(match.group(1))
        results: list[JobDict] = []

        for key, listing in apollo.items():
            if not key.startswith("JobListing:"):
                continue
            try:
                title   = str(listing.get("title") or listing.get("name") or "").strip()
                company = _extract_company_name(apollo, listing)
                if not title or not company:
                    continue

                apply_url = str(listing.get("applyUrl") or listing.get("apply_url") or "").strip()
                if not apply_url:
                    slug = listing.get("slug") or key.split(":")[-1]
                    apply_url = f"https://wellfound.com/jobs/{slug}"

                locations_raw = listing.get("locationNames") or listing.get("locations") or []
                if isinstance(locations_raw, list):
                    location = ", ".join(str(l) for l in locations_raw if l) or "Remote"
                else:
                    location = str(locations_raw) or "Remote"

                is_remote = bool(listing.get("remote") or listing.get("isRemote") or "remote" in location.lower())
                job_type  = _classify_job_type(listing)

                salary_raw = str(listing.get("salary") or listing.get("compensation") or "").strip()

                job = JobDict(
                    title=title,
                    company=company,
                    location=location,
                    url=apply_url,
                    source="Wellfound",
                    job_type=job_type,  # type: ignore[typeddict-item]
                    date_posted="Recent",
                    is_remote=is_remote,
                )
                if salary_raw:
                    if job_type == "internship":
                        job["stipend"] = salary_raw
                    else:
                        job["salary"] = salary_raw

                results.append(job)

            except Exception as e:
                logger.debug(f"Wellfound listing parse error: {e}")

        return results

    except Exception as e:
        logger.error(f"Wellfound error for role '{role}': {e}")
        return []


def scrape_wellfound() -> list[JobDict]:
    roles = load_config()["search"].get("wellfound_roles", [])
    results: list[JobDict] = []
    seen_urls: set[str] = set()

    for role in roles:
        jobs = _scrape_role(role)
        for job in jobs:
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                results.append(job)
        time.sleep(2)

    logger.info(f"Wellfound: {len(results)} results")
    return results
