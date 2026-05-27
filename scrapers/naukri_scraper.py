"""
Naukri.com scraper — internship and fresher tech roles in India.
Uses the unofficial JSON search API (same endpoint as their mobile app).
Falls back to HTML parsing if the API is blocked.
"""

import logging
import time
import re

import requests
from bs4 import BeautifulSoup

from .base import JobDict
from config_manager import load_config

logger = logging.getLogger(__name__)

_API_URL  = "https://www.naukri.com/jobapi/v3/search"
_SEARCH_URL = "https://www.naukri.com/{slug}-jobs-in-india?experience=0&freshness=1"

_HEADERS_API = {
    "User-Agent":   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "appid":        "109",
    "systemid":     "109",
    "Content-Type": "application/json",
    "Accept":       "application/json",
}
_HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _api_search(keyword: str) -> list[JobDict]:
    params = {
        "noOfResults":  20,
        "urlType":      "search_by_keyword",
        "searchType":   "adv",
        "keyword":      keyword,
        "experience":   0,
        "freshness":    1,
    }
    try:
        resp = requests.get(_API_URL, params=params, headers=_HEADERS_API, timeout=12)
        if resp.status_code != 200:
            return []
        data = resp.json()
        jobs_raw = data.get("jobDetails") or data.get("jobs") or []
        results: list[JobDict] = []
        for j in jobs_raw:
            url = j.get("jdURL") or j.get("jobUrl") or ""
            if not url.startswith("http"):
                url = "https://www.naukri.com" + url
            title   = j.get("title") or j.get("jobTitle") or ""
            company = (j.get("companyName") or j.get("company") or {})
            if isinstance(company, dict):
                company = company.get("name", "")
            location = ", ".join(j.get("placeholders", [{}])[0].get("label", "").split(",")[:2]) if j.get("placeholders") else ""
            results.append(JobDict(
                title=str(title).strip(),
                company=str(company).strip(),
                location=str(location).strip() or "India",
                url=url,
                source="Naukri",
                job_type="internship",
                stipend="",
                date_posted=str(j.get("createdDate", "")),
                paid=None,
                is_remote=False,
            ))
        return results
    except Exception as e:
        logger.debug(f"Naukri API error for '{keyword}': {e}")
        return []


def _html_search(slug: str) -> list[JobDict]:
    url = _SEARCH_URL.format(slug=slug)
    try:
        resp = requests.get(url, headers=_HEADERS_HTML, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results: list[JobDict] = []

        # Try multiple card selectors (Naukri has changed layout several times)
        cards = (
            soup.select("article.jobTuple")
            or soup.select("div.srp-jobtuple-wrapper")
            or soup.select("div[class*='job-tuple']")
            or soup.select("article[class*='jobTuple']")
        )
        for card in cards[:15]:
            try:
                title_el = (
                    card.select_one("a.title")
                    or card.select_one("a[class*='title']")
                    or card.select_one("a.job-title")
                )
                company_el = (
                    card.select_one("a.subTitle")
                    or card.select_one("a[class*='company']")
                    or card.select_one("span[class*='company']")
                )
                loc_el = (
                    card.select_one("span.locWdth")
                    or card.select_one("span[class*='location']")
                    or card.select_one("li[class*='location']")
                )
                href = title_el.get("href", "") if title_el else ""
                if not href.startswith("http"):
                    href = "https://www.naukri.com" + href

                results.append(JobDict(
                    title=(title_el.get_text(strip=True) if title_el else "").strip(),
                    company=(company_el.get_text(strip=True) if company_el else "").strip(),
                    location=(loc_el.get_text(strip=True) if loc_el else "India").strip(),
                    url=href,
                    source="Naukri",
                    job_type="internship",
                    stipend="",
                    date_posted="",
                    paid=None,
                    is_remote=False,
                ))
            except Exception:
                continue
        return results
    except Exception as e:
        logger.debug(f"Naukri HTML scrape error for '{slug}': {e}")
        return []


def scrape_naukri() -> list[JobDict]:
    cfg      = load_config()
    keywords = cfg["search"].get("naukri_keywords", [
        "software engineer intern",
        "sde intern",
        "developer intern",
        "full stack intern",
        "machine learning intern",
    ])
    seen_urls: set[str] = set()
    all_jobs: list[JobDict] = []

    for kw in keywords:
        # Try API first
        jobs = _api_search(kw)
        if not jobs:
            # Fall back to HTML with slug form of keyword
            slug = re.sub(r"\s+", "-", kw.strip().lower())
            jobs = _html_search(slug)

        for j in jobs:
            if j["url"] and j["url"] not in seen_urls and j["title"]:
                seen_urls.add(j["url"])
                all_jobs.append(j)
        time.sleep(0.8)

    logger.info(f"Naukri: scraped {len(all_jobs)} raw jobs")
    return all_jobs
