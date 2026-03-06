import logging
import os
import time
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

KEYWORDS = [
    "software engineer intern",
    "software developer intern",
    "sde intern",
    "full stack developer intern",
    "frontend developer intern",
    "backend developer intern",
    "devops intern",
    "machine learning intern",
    "ai engineer intern",
    "data engineer intern",
]

LOCATIONS = ["India", "Remote", "United States"]
MAX_PAGES_PER_QUERY = int(os.environ.get("LINKEDIN_MAX_PAGES", "1"))
RESULTS_PER_PAGE = 25


def _build_guest_url(keyword: str, location: str, start: int) -> str:
    params = {
        "keywords": keyword,
        "location": location,
        "start": start,
        "f_TPR": "r604800",  # last 7 days
        "f_E": "1,2",  # internship/entry level-ish
    }
    return f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{urlencode(params)}"


def _parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("li")

    jobs = []
    for card in cards:
        link_el = card.select_one("a.base-card__full-link, a.base-card-link") or card.select_one("a[href]")
        title_el = card.select_one("h3.base-search-card__title") or card.select_one("h3")
        company_el = card.select_one("h4.base-search-card__subtitle") or card.select_one("h4")
        location_el = card.select_one("span.job-search-card__location") or card.select_one(".job-search-card__location")
        date_el = card.select_one("time")

        url = (link_el.get("href") or "").strip() if link_el else ""
        if not url:
            continue

        jobs.append(
            {
                "title": title_el.get_text(" ", strip=True) if title_el else "N/A",
                "company": company_el.get_text(" ", strip=True) if company_el else "N/A",
                "location": location_el.get_text(" ", strip=True) if location_el else "N/A",
                "url": url,
                "source": "LinkedIn",
                "date_posted": date_el.get("datetime", "Recent") if date_el else "Recent",
            }
        )

    return jobs


def scrape_linkedin() -> list[dict]:
    results: list[dict] = []
    seen_urls: set[str] = set()

    for keyword in KEYWORDS:
        for location in LOCATIONS:
            for page in range(MAX_PAGES_PER_QUERY):
                start = page * RESULTS_PER_PAGE
                url = _build_guest_url(keyword, location, start)

                try:
                    response = requests.get(url, headers=HEADERS, timeout=20)
                    response.raise_for_status()
                    parsed = _parse_cards(response.text)

                    new_count = 0
                    for job in parsed:
                        job_url = job.get("url", "")
                        if not job_url or job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)
                        results.append(job)
                        new_count += 1

                    logger.info(
                        "LinkedIn guest scrape: keyword='%s' location='%s' page=%s parsed=%s new=%s",
                        keyword,
                        location,
                        page + 1,
                        len(parsed),
                        new_count,
                    )

                    # If a page has no cards, remaining pages are usually empty too.
                    if not parsed:
                        break

                    time.sleep(1.0)
                except Exception as error:
                    logger.error(
                        "LinkedIn guest scrape failed: keyword='%s' location='%s' page=%s error=%s",
                        keyword,
                        location,
                        page + 1,
                        error,
                    )
                    break

    logger.info("LinkedIn scraping done. Found %s unique results.", len(results))
    return results
