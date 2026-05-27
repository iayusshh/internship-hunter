"""
Turing remote jobs scraper.
Fetches static HTML category pages and extracts remote developer role listings.
All results are full_time_remote (Turing is a remote-first talent marketplace).
"""

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

_ROLE_TITLES = {
    "remote-software-engineer-jobs":        "Software Engineer",
    "remote-full-stack-jobs":               "Full Stack Developer",
    "remote-machine-learning-engineer-jobs": "Machine Learning Engineer",
    "remote-backend-developer-jobs":        "Backend Developer",
    "remote-frontend-developer-jobs":       "Frontend Developer",
    "remote-devops-engineer-jobs":          "DevOps Engineer",
    "remote-data-engineer-jobs":            "Data Engineer",
}


def _infer_title(url: str) -> str:
    for slug, title in _ROLE_TITLES.items():
        if slug in url:
            return title
    slug = url.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").replace("remote", "").strip().title()


def _scrape_page(page_url: str) -> list[JobDict]:
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        results: list[JobDict] = []
        default_title = _infer_title(page_url)

        # Turing renders role cards — try multiple selector strategies
        cards = (
            soup.select(".job-card")
            or soup.select("[class*='JobCard']")
            or soup.select("[class*='job-card']")
            or soup.select("article")
        )

        if cards:
            for card in cards:
                try:
                    title_el   = card.select_one("h2, h3, [class*='title'], [class*='role']")
                    company_el = card.select_one("[class*='company'], [class*='client']")
                    salary_el  = card.select_one("[class*='salary'], [class*='pay'], [class*='rate']")
                    link_el    = card.select_one("a[href]")

                    title   = title_el.get_text(strip=True) if title_el else default_title
                    company = company_el.get_text(strip=True) if company_el else "Turing Client"
                    salary  = salary_el.get_text(strip=True) if salary_el else ""
                    href    = link_el["href"] if link_el else page_url
                    url     = f"https://www.turing.com{href}" if href.startswith("/") else href or page_url

                    if not title:
                        title = default_title

                    job = JobDict(
                        title=title,
                        company=company,
                        location="Remote",
                        url=url,
                        source="Turing",
                        job_type="full_time_remote",
                        date_posted="Recent",
                        is_remote=True,
                    )
                    if salary:
                        job["salary"] = salary

                    results.append(job)

                except Exception as e:
                    logger.debug(f"Turing card parse error: {e}")

        else:
            # No cards found — create a single representative listing for this role category
            results.append(JobDict(
                title=default_title,
                company="Turing Client Companies",
                location="Remote (Worldwide)",
                url=page_url,
                source="Turing",
                job_type="full_time_remote",
                date_posted="Recent",
                is_remote=True,
            ))

        return results

    except Exception as e:
        logger.error(f"Turing error for {page_url}: {e}")
        return []


def scrape_turing() -> list[JobDict]:
    urls = load_config()["search"].get("turing_urls", [])
    results: list[JobDict] = []
    seen_urls: set[str] = set()

    for page_url in urls:
        jobs = _scrape_page(page_url)
        for job in jobs:
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                results.append(job)
        time.sleep(1.5)

    logger.info(f"Turing: {len(results)} results")
    return results
