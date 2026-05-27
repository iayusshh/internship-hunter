import requests
import logging
import time

from config_manager import load_config
from scrapers.base import JobDict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://unstop.com/",
}


def _extract_stipend(item: dict) -> str:
    for key in ("stipend", "stipend_salary", "salary", "rewards", "currency_package"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)):
            return str(val)
    return ""


def _extract_paid_flag(item: dict):
    for key in ("is_paid", "paid", "is_stipend", "has_stipend"):
        val = item.get(key)
        if isinstance(val, bool):
            return val
    return None


def scrape_unstop() -> list[JobDict]:
    keywords = load_config()["search"]["unstop_keywords"]
    results: list[JobDict] = []
    seen_ids: set[str] = set()

    for keyword in keywords:
        try:
            resp = requests.get(
                "https://unstop.com/api/public/opportunity/search-result",
                headers=HEADERS,
                params={
                    "opportunity": "jobs",
                    "search": keyword,
                    "per_page": 20,
                    "page": 1,
                    "filterByType": "2",
                    "filterByWorkplace": "1,2,3",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            items = (
                data.get("data", {}).get("data", [])
                or data.get("data", [])
                or []
            )

            for item in items:
                try:
                    opp_id = str(item.get("id", ""))
                    if opp_id in seen_ids:
                        continue
                    seen_ids.add(opp_id)

                    title   = item.get("title") or item.get("job_title") or "N/A"
                    org     = item.get("organisation", {})
                    company = org.get("name") if isinstance(org, dict) else str(org or "N/A")
                    location = item.get("location") or item.get("city") or "Remote"
                    stipend = _extract_stipend(item)
                    paid    = _extract_paid_flag(item)
                    slug    = item.get("public_url") or item.get("slug") or ""
                    url     = (
                        f"https://unstop.com/{slug}" if slug and not slug.startswith("http")
                        else slug or f"https://unstop.com/jobs/{opp_id}"
                    )

                    results.append(JobDict(
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        source="Unstop",
                        job_type="internship",
                        date_posted=item.get("start_date") or "Recent",
                        stipend=stipend,
                        paid=paid,
                    ))
                except Exception as e:
                    logger.debug(f"Unstop item parse error: {e}")

            time.sleep(1.5)

        except Exception as e:
            logger.error(f"Unstop error for '{keyword}': {e}")

    logger.info(f"Unstop: {len(results)} results")
    return results
