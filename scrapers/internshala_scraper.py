import requests
from bs4 import BeautifulSoup
import logging
import time

from config_manager import load_config
from scrapers.base import JobDict

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_stipend(card) -> str:
    el = (
        card.select_one(".stipend")
        or card.select_one(".salary")
        or card.select_one(".item_body")
    )
    return el.get_text(" ", strip=True) if el else ""


def scrape_internshala() -> list[JobDict]:
    terms = load_config()["search"]["internshala_terms"]
    results: list[JobDict] = []
    seen_urls: set[str] = set()

    for term in terms:
        urls = [
            f"https://internshala.com/internships/{term}-internship/work-from-home-jobs",
            f"https://internshala.com/internships/{term}-internship",
        ]
        for url in urls:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select(".individual_internship") or soup.select(".internship_meta")

                for card in cards:
                    try:
                        title_el   = card.select_one(".job-internship-name") or card.select_one("h3")
                        company_el = card.select_one(".company-name") or card.select_one(".companyName")
                        loc_el     = card.select_one(".location_link") or card.select_one(".location")
                        link_el    = card.select_one("a[href]")
                        stipend    = _extract_stipend(card)

                        title   = title_el.get_text(strip=True)   if title_el   else "N/A"
                        company = company_el.get_text(strip=True)  if company_el else "N/A"
                        location = loc_el.get_text(strip=True)     if loc_el     else "Work From Home"
                        href    = link_el["href"]                  if link_el    else ""
                        full_url = f"https://internshala.com{href}" if href.startswith("/") else href

                        if full_url and full_url not in seen_urls:
                            seen_urls.add(full_url)
                            results.append(JobDict(
                                title=title,
                                company=company,
                                location=location,
                                url=full_url,
                                source="Internshala",
                                job_type="internship",
                                date_posted="Recent",
                                stipend=stipend,
                            ))
                    except Exception as e:
                        logger.debug(f"Internshala card parse error: {e}")

                time.sleep(1.5)

            except Exception as e:
                logger.error(f"Internshala error for '{term}' at '{url}': {e}")

    logger.info(f"Internshala: {len(results)} results")
    return results
