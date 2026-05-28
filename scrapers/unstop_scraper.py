"""
Unstop scraper — internship listings and hackathons.
Uses Playwright to get a real browser session, then intercepts the API response.
Same approach as naukri_scraper.py to bypass bot protection.
"""

import logging
import time
from urllib.parse import quote_plus

from .base import JobDict
from config_manager import load_config

logger = logging.getLogger(__name__)

_STEALTH_SCRIPT = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _extract_stipend(item: dict) -> str:
    for key in ("stipend", "stipend_salary", "salary", "rewards", "currency_package"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)) and val:
            return str(val)
    return ""


def _extract_prize(item: dict) -> str:
    for key in ("reward", "prizes", "prize_money", "prize", "cash_prize", "rewards", "stipend"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)) and val:
            return f"₹{int(val):,}"
    return ""


def _extract_paid_flag(item: dict):
    for key in ("isPaid", "is_paid", "paid", "is_stipend", "has_stipend"):
        val = item.get(key)
        if isinstance(val, bool):
            return val
    return None


def _extract_items(data: dict) -> list:
    return (
        data.get("data", {}).get("data", [])
        or data.get("data", [])
        or []
    )


def _build_url(item: dict, opp_id: str) -> str:
    slug = item.get("public_url") or item.get("slug") or ""
    if slug and not slug.startswith("http"):
        return f"https://unstop.com/{slug.lstrip('/')}"
    return slug or f"https://unstop.com/opportunity/{opp_id}"


def _get_company(item: dict) -> str:
    org = item.get("organisation", {})
    return org.get("name") if isinstance(org, dict) else str(org or "N/A")


def _launch_browser(pw):
    try:
        return pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
        )
    except Exception as e:
        logger.warning(f"Unstop: system Chrome not available — skipping ({e})")
        return None


def scrape_unstop() -> list[JobDict]:
    from playwright.sync_api import sync_playwright

    keywords = load_config()["search"].get("unstop_keywords", [
        "software engineer", "full stack", "developer", "frontend", "backend",
        "artificial intelligence", "machine learning",
    ])

    results: list[JobDict] = []
    seen_ids: set[str] = set()

    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        if not browser:
            return []

        ctx = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 800}, locale="en-US")
        page = ctx.new_page()
        page.add_init_script(_STEALTH_SCRIPT)

        for keyword in keywords:
            try:
                captured: dict = {}

                def _on_resp(response, cap=captured):
                    if "opportunity/search-result" in response.url and response.status == 200:
                        try:
                            cap["data"] = response.json()
                        except Exception:
                            pass

                page.on("response", _on_resp)
                page.goto(
                    f"https://unstop.com/jobs?opportunity=jobs&searchTerm={quote_plus(keyword)}",
                    wait_until="domcontentloaded",
                    timeout=25000,
                )
                page.wait_for_timeout(2500)
                page.remove_listener("response", _on_resp)

                items = _extract_items(captured.get("data", {}))
                logger.info(f"Unstop jobs '{keyword}': {len(items)} raw items")

                for item in items:
                    try:
                        opp_id = str(item.get("id", ""))
                        if not opp_id or opp_id in seen_ids:
                            continue
                        seen_ids.add(opp_id)

                        results.append(JobDict(
                            title=item.get("title") or item.get("job_title") or "N/A",
                            company=_get_company(item),
                            location=item.get("location") or item.get("city") or "India",
                            url=_build_url(item, opp_id),
                            source="Unstop",
                            job_type="internship",
                            date_posted=str(item.get("start_date") or "Recent"),
                            stipend=_extract_stipend(item),
                            paid=_extract_paid_flag(item),
                        ))
                    except Exception as e:
                        logger.debug(f"Unstop job parse error: {e}")

                time.sleep(1.5)
            except Exception as e:
                logger.error(f"Unstop jobs error for '{keyword}': {e}")

        browser.close()

    logger.info(f"Unstop: {len(results)} job results")
    return results


def scrape_unstop_hackathons() -> list[JobDict]:
    from playwright.sync_api import sync_playwright

    keywords = load_config()["search"].get("unstop_hackathon_keywords", [
        "machine learning", "web development", "data science", "software", "ai", "open innovation",
    ])

    results: list[JobDict] = []
    seen_ids: set[str] = set()

    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        if not browser:
            return []

        ctx = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 800}, locale="en-US")
        page = ctx.new_page()
        page.add_init_script(_STEALTH_SCRIPT)

        for keyword in keywords:
            try:
                captured: dict = {}

                def _on_resp(response, cap=captured):
                    if "opportunity/search-result" in response.url and response.status == 200:
                        try:
                            cap["data"] = response.json()
                        except Exception:
                            pass

                page.on("response", _on_resp)
                page.goto(
                    f"https://unstop.com/hackathons?opportunity=hackathon&searchTerm={quote_plus(keyword)}",
                    wait_until="domcontentloaded",
                    timeout=25000,
                )
                page.wait_for_timeout(2500)
                page.remove_listener("response", _on_resp)

                items = _extract_items(captured.get("data", {}))
                logger.info(f"Unstop hackathons '{keyword}': {len(items)} raw items")

                for item in items:
                    try:
                        opp_id = str(item.get("id", ""))
                        if not opp_id or opp_id in seen_ids:
                            continue
                        seen_ids.add(opp_id)

                        mode = str(item.get("mode", "") or item.get("hackathon_mode", "") or "").lower()
                        is_online = "online" in mode or not mode
                        location = "Online" if is_online else (item.get("city") or item.get("location") or "India")

                        deadline = str(
                            item.get("registration_deadline")
                            or item.get("end_date")
                            or item.get("registration_end")
                            or "Check website"
                        )

                        results.append(JobDict(
                            title=item.get("title") or "N/A",
                            company=_get_company(item),
                            location=location,
                            url=_build_url(item, opp_id),
                            source="Unstop Hackathons",
                            job_type="hackathon",
                            date_posted=deadline,
                            stipend=_extract_prize(item),
                            is_remote=is_online,
                        ))
                    except Exception as e:
                        logger.debug(f"Unstop hackathon parse error: {e}")

                time.sleep(1.5)
            except Exception as e:
                logger.error(f"Unstop hackathons error for '{keyword}': {e}")

        browser.close()

    logger.info(f"Unstop Hackathons: {len(results)} results")
    return results
