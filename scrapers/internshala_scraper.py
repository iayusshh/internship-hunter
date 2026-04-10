import requests
from bs4 import BeautifulSoup
import logging
import time

from config_manager import load_config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_search_terms() -> list[str]:
    return load_config()["search"]["internshala_terms"]


def _extract_stipend_text(card) -> str:
    stipend_el = (
        card.select_one(".stipend")
        or card.select_one(".salary")
        or card.select_one(".item_body")
    )
    return stipend_el.get_text(" ", strip=True) if stipend_el else ""

def scrape_internshala() -> list[dict]:
    results = []
    seen_urls = set()

    for term in _get_search_terms():
        # Cover both remote and on-site listings.
        urls = [
            f"https://internshala.com/internships/{term}-internship/work-from-home-jobs",
            f"https://internshala.com/internships/{term}-internship",
        ]
        for url in urls:
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")
                cards = soup.select(".individual_internship") or soup.select(".internship_meta")

                for card in cards:
                    try:
                        title_el = card.select_one(".job-internship-name") or card.select_one("h3")
                        company_el = card.select_one(".company-name") or card.select_one(".companyName")
                        location_el = card.select_one(".location_link") or card.select_one(".location")
                        link_el = card.select_one("a[href]")
                        stipend_text = _extract_stipend_text(card)

                        title = title_el.get_text(strip=True) if title_el else "N/A"
                        company = company_el.get_text(strip=True) if company_el else "N/A"
                        location = location_el.get_text(strip=True) if location_el else "Work From Home"
                        href = link_el["href"] if link_el else ""
                        full_url = f"https://internshala.com{href}" if href.startswith("/") else href

                        if full_url and full_url not in seen_urls:
                            seen_urls.add(full_url)
                            results.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": full_url,
                                "source": "Internshala",
                                "date_posted": "Recent",
                                "stipend": stipend_text,
                            })
                    except Exception as e:
                        logger.warning(f"Error parsing Internshala card: {e}")
                        continue

                time.sleep(1.5)

            except Exception as e:
                logger.error(f"Error scraping Internshala for '{term}' at '{url}': {e}")
                continue

    logger.info(f"Internshala scraping done. Found {len(results)} results.")
    return results
