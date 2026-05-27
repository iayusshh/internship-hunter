"""
Referral finder — surfaces 2nd-degree LinkedIn connections at a target company.

Two modes:
1. URL mode (default): generate a LinkedIn search URL the user opens manually
2. Playwright mode (opt-in): actually scrapes results using the user's LinkedIn session
"""

import logging
import urllib.parse

logger = logging.getLogger(__name__)


def linkedin_search_url(company: str) -> str:
    """Return a LinkedIn people search URL pre-filtered to 2nd-degree connections at company."""
    params = urllib.parse.urlencode({
        "keywords": company,
        "network":  '["S"]',   # 2nd-degree ("S" = second)
        "origin":   "FACETED_SEARCH",
    })
    return f"https://www.linkedin.com/search/results/people/?{params}"


def find_referrals_playwright(
    company: str,
    email: str,
    password: str,
    headless: bool = True,
    max_results: int = 5,
) -> list[dict]:
    """
    Scrape LinkedIn search results for 2nd-degree connections at `company`.
    Returns list of {name, title, profile_url}.
    Requires LINKEDIN_EMAIL + LINKEDIN_PASSWORD env vars.
    """
    results: list[dict] = []
    try:
        from playwright.sync_api import sync_playwright
        import os, random, time

        search_url = linkedin_search_url(company)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            # Login
            page.goto("https://www.linkedin.com/login", timeout=30000)
            time.sleep(random.uniform(1, 2))
            page.fill("input#username", email)
            time.sleep(random.uniform(0.3, 0.7))
            page.fill("input#password", password)
            time.sleep(random.uniform(0.4, 0.8))
            page.click("button[type='submit']")
            time.sleep(random.uniform(2, 4))

            if "login" in page.url:
                logger.warning("Referral finder: LinkedIn login failed")
                browser.close()
                return []

            # Search
            page.goto(search_url, timeout=30000)
            time.sleep(random.uniform(2, 3))

            cards = page.query_selector_all(".reusable-search__result-container, li.search-result")
            for card in cards[:max_results]:
                try:
                    name_el    = card.query_selector("span.actor-name, .entity-result__title-text a")
                    title_el   = card.query_selector(".entity-result__primary-subtitle, .subline-level-1")
                    profile_el = card.query_selector("a.app-aware-link, a[data-control-name='search_srp_result']")
                    results.append({
                        "name":        (name_el.inner_text()    if name_el    else "").strip(),
                        "title":       (title_el.inner_text()   if title_el   else "").strip(),
                        "profile_url": (profile_el.get_attribute("href") or "") if profile_el else "",
                    })
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Referral Playwright scrape failed: {e}")

    return [r for r in results if r["name"]]


def find_referrals(company: str, use_playwright: bool = False, **kwargs) -> list[dict]:
    """
    Entry point. Returns a list of referral dicts.
    If use_playwright is False or Playwright fails, returns an empty list
    (caller should fall back to showing the linkedin_search_url).
    """
    if not use_playwright:
        return []
    import os
    email    = kwargs.get("email")    or os.environ.get("LINKEDIN_EMAIL", "")
    password = kwargs.get("password") or os.environ.get("LINKEDIN_PASSWORD", "")
    if not email or not password:
        return []
    return find_referrals_playwright(
        company, email, password,
        headless=kwargs.get("headless", True),
        max_results=kwargs.get("max_results", 5),
    )
