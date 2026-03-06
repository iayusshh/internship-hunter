import requests
from bs4 import BeautifulSoup
import logging
import time

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://unstop.com/",
}

SEARCH_KEYWORDS = [
    "software engineer",
    "full stack",
    "developer",
    "frontend",
    "backend",
    "artificial intelligence",
    "machine learning",
]

def scrape_unstop() -> list[dict]:
    results = []
    seen_ids = set()

    for keyword in SEARCH_KEYWORDS:
        try:
            # Unstop public API endpoint for jobs/internships
            api_url = "https://unstop.com/api/public/opportunity/search-result"
            params = {
                "opportunity": "jobs",
                "search": keyword,
                "per_page": 20,
                "page": 1,
                "filterByType": "2",         # 2 = Internship
                "filterByWorkplace": "1,2",  # 1=Remote, 2=Hybrid
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
                    slug = item.get("public_url") or item.get("slug") or ""
                    url = f"https://unstop.com/{slug}" if slug and not slug.startswith("http") else slug or f"https://unstop.com/jobs/{opp_id}"

                    results.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "source": "Unstop",
                        "date_posted": item.get("start_date") or "Recent",
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
