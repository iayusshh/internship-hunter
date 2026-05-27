"""
Naukri.com scraper — internship and fresher tech roles in India.
Uses system Chrome via Playwright to bypass Akamai bot protection.
The browser renders the page and we intercept the jobapi/v3/search response.
Falls back gracefully if system Chrome is not installed.
"""

import logging
import re
import time

from .base import JobDict
from config_manager import load_config

logger = logging.getLogger(__name__)

_STEALTH_SCRIPT = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"


def _parse_api_response(data: dict) -> list[JobDict]:
    jobs_raw = data.get("jobDetails", [])
    results: list[JobDict] = []

    for j in jobs_raw:
        try:
            title   = str(j.get("title", "")).strip()
            company = str(j.get("companyName", "")).strip()
            if not title or not company:
                continue

            url_path = j.get("jdURL", "")
            job_url = url_path if url_path.startswith("http") else f"https://www.naukri.com{url_path}"

            location = "India"
            stipend  = ""
            paid     = None

            for ph in j.get("placeholders", []):
                ph_type = ph.get("type", "")
                label   = str(ph.get("label", "")).strip()
                if ph_type == "location" and label:
                    location = label
                elif ph_type == "salary":
                    if label.lower() in ("unpaid", ""):
                        paid = False
                    else:
                        stipend = label
                        paid    = True

            results.append(JobDict(
                title=title,
                company=company,
                location=location,
                url=job_url,
                source="Naukri",
                job_type="internship",
                stipend=stipend,
                date_posted=str(j.get("createdDate", "")),
                paid=paid,
                is_remote="remote" in location.lower(),
            ))
        except Exception as e:
            logger.debug(f"Naukri job parse error: {e}")

    return results


def scrape_naukri() -> list[JobDict]:
    from playwright.sync_api import sync_playwright

    cfg      = load_config()
    keywords = cfg["search"].get("naukri_keywords", [
        "software engineer intern",
        "sde intern",
        "developer intern",
        "full stack intern",
        "machine learning intern",
    ])

    all_jobs:  list[JobDict] = []
    seen_urls: set[str]      = set()

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
            )
        except Exception as e:
            logger.warning(f"Naukri: system Chrome not available — skipping ({e})")
            return []

        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = ctx.new_page()
        page.add_init_script(_STEALTH_SCRIPT)

        for kw in keywords:
            try:
                slug = re.sub(r"\s+", "-", kw.strip().lower())
                url  = f"https://www.naukri.com/{slug}-jobs"

                captured: dict = {}

                def _on_resp(response, cap=captured):
                    if "jobapi/v3/search" in response.url and response.status == 200:
                        try:
                            cap["data"] = response.json()
                        except Exception:
                            pass

                page.on("response", _on_resp)
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2500)
                page.remove_listener("response", _on_resp)

                jobs = _parse_api_response(captured.get("data", {}))
                logger.info(f"Naukri '{kw}': {len(jobs)} raw jobs")
                for j in jobs:
                    if j["url"] and j["url"] not in seen_urls and j["title"]:
                        seen_urls.add(j["url"])
                        all_jobs.append(j)

                time.sleep(1.5)

            except Exception as e:
                logger.error(f"Naukri error for '{kw}': {e}")

        browser.close()

    logger.info(f"Naukri: {len(all_jobs)} total jobs scraped")
    return all_jobs
