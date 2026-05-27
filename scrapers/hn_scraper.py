"""
HackerNews "Ask HN: Who is Hiring?" scraper.
Finds the latest monthly thread, extracts job comments, filters by keywords.
"""

import html as html_module
import logging
import re
import time

import requests

from .base import JobDict
from config_manager import load_config

logger = logging.getLogger(__name__)

_ALGOLIA_URL  = "https://hn.algolia.com/api/v1/search_by_date"
_HN_ITEM_URL  = "https://hacker-news.firebaseio.com/v0/item/{}.json"
_HN_POST_BASE = "https://news.ycombinator.com/item?id={}"


def _find_latest_hiring_thread() -> int | None:
    """Return the HN item ID of the most recent 'Ask HN: Who is Hiring?' thread."""
    try:
        resp = requests.get(
            _ALGOLIA_URL,
            params={
                "tags":        "ask_hn",
                "query":       "Ask HN: Who is Hiring",
                "hitsPerPage": 3,
            },
            timeout=10,
        )
        hits = resp.json().get("hits", [])
        for hit in hits:
            title = (hit.get("title") or "").lower()
            if "who is hiring" in title:
                return int(hit["objectID"])
    except Exception as e:
        logger.debug(f"HN Algolia search failed: {e}")
    return None


def _fetch_item(item_id: int) -> dict:
    try:
        resp = requests.get(_HN_ITEM_URL.format(item_id), timeout=8)
        return resp.json() or {}
    except Exception:
        return {}


def _clean_html(text: str) -> str:
    text = html_module.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _extract_url(text: str) -> str:
    match = re.search(r'https?://\S+', text)
    if match:
        url = match.group().rstrip(".,)")
        return url
    return ""


def _is_relevant(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


def _parse_comment(text: str) -> JobDict | None:
    """Parse a free-form HN job comment into a JobDict."""
    clean = _clean_html(text)
    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    if not lines:
        return None

    url = _extract_url(clean)
    if not url:
        return None

    # Try pipe-separated format: Company | Role | Location | ...
    first_line = lines[0]
    parts = [p.strip() for p in first_line.split("|")]

    if len(parts) >= 2:
        company = parts[0].strip()
        role    = parts[1].strip()
        location_hint = parts[2].strip() if len(parts) > 2 else ""
    else:
        # Fall back: first non-empty line = company/role mixture
        company = first_line[:80]
        role    = "Software Engineer"
        location_hint = ""

    is_intern = any(t in clean.lower() for t in ("intern", "internship", "co-op", "coop"))
    is_remote = any(t in clean.lower() for t in ("remote", "anywhere", "worldwide"))
    job_type  = "internship" if is_intern else "full_time_remote"

    if not is_remote and job_type == "full_time_remote":
        return None  # skip on-site full-time roles

    return JobDict(
        title=role[:120],
        company=company[:120],
        location=location_hint or ("Remote" if is_remote else "Onsite"),
        url=url,
        source="HN Jobs",
        job_type=job_type,
        stipend="",
        salary="",
        date_posted="",
        paid=True,
        is_remote=is_remote,
    )


def scrape_hn() -> list[JobDict]:
    cfg      = load_config()
    keywords = cfg["search"].get("hn_hiring_keywords", [
        "python", "javascript", "typescript", "react", "node", "backend",
        "frontend", "full stack", "ml", "machine learning", "intern",
        "remote", "software engineer", "developer",
    ])
    cap = int(cfg["search"].get("hn_results_cap", 20))

    thread_id = _find_latest_hiring_thread()
    if not thread_id:
        logger.warning("HN: could not find 'Who is Hiring?' thread")
        return []

    thread = _fetch_item(thread_id)
    kid_ids = thread.get("kids", [])[:300]
    logger.info(f"HN: found thread {thread_id} with {len(kid_ids)} comments")

    results: list[JobDict] = []
    seen_urls: set[str] = set()

    for kid_id in kid_ids:
        if len(results) >= cap:
            break
        comment = _fetch_item(kid_id)
        if comment.get("deleted") or comment.get("dead"):
            continue
        text = comment.get("text", "")
        if not _is_relevant(text, keywords):
            continue

        job = _parse_comment(text)
        if job and job["url"] and job["url"] not in seen_urls and job["title"]:
            seen_urls.add(job["url"])
            results.append(job)

        time.sleep(0.05)  # be gentle on the Firebase API

    logger.info(f"HN: scraped {len(results)} relevant jobs")
    return results
