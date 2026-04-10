import requests
import logging
import time

from config_manager import load_config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://unstop.com/",
}


def _get_search_keywords() -> list[str]:
    return load_config()["search"]["unstop_keywords"]


def _extract_unstop_stipend(item: dict) -> str:
    stipend_candidates = [
        item.get("stipend"),
        item.get("stipend_salary"),
        item.get("salary"),
        item.get("rewards"),
        item.get("currency_package"),
    ]
    for value in stipend_candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def _extract_unstop_paid_flag(item: dict) -> bool | None:
    for key in ["is_paid", "paid", "is_stipend", "has_stipend"]:
        value = item.get(key)
        if isinstance(value, bool):
            return value
    return None

def scrape_unstop() -> list[dict]:
    results = []
    seen_ids = set()

    for keyword in _get_search_keywords():
        try:
            api_url = "https://unstop.com/api/public/opportunity/search-result"
            params = {
                "opportunity": "jobs",
                "search": keyword,
                "per_page": 20,
                "page": 1,
                "filterByType": "2",         # 2 = Internship
                "filterByWorkplace": "1,2,3",  # 1=Remote, 2=Hybrid, 3=On-site
            }

            response = requests.get(api_url, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

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

                    title = item.get("title") or item.get("job_title") or "N/A"
                    org = item.get("organisation", {})
                    company = org.get("name") if isinstance(org, dict) else str(org or "N/A")
                    location = item.get("location") or item.get("city") or "Remote"
                    stipend = _extract_unstop_stipend(item)
                    paid = _extract_unstop_paid_flag(item)
                    slug = item.get("public_url") or item.get("slug") or ""
                    url = f"https://unstop.com/{slug}" if slug and not slug.startswith("http") else slug or f"https://unstop.com/jobs/{opp_id}"

                    results.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "source": "Unstop",
                        "date_posted": item.get("start_date") or "Recent",
                        "stipend": stipend,
                        "paid": paid,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing Unstop item: {e}")
                    continue

            time.sleep(1.5)

        except Exception as e:
            logger.error(f"Error scraping Unstop for '{keyword}': {e}")
            continue

    logger.info(f"Unstop scraping done. Found {len(results)} results.")
    return results
