import os
import logging
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
from linkedin_jobs_scraper.filters import (
    RelevanceFilters,
    TimeFilters,
    TypeFilters,
    ExperienceLevelFilters,
    OnSiteOrRemoteFilters,
)

logger = logging.getLogger(__name__)

KEYWORDS = [
    "software engineer intern",
    "full stack intern",
    "developer intern",
    "frontend intern",
    "backend intern",
    "AI intern",
    "ML intern",
    "fresher developer",
]

LOCATIONS = ["India", "Worldwide"]


def scrape_linkedin() -> list[dict]:
    results = []
    li_at = os.environ.get("LI_AT_COOKIE", "")

    def on_data(data: EventData):
        results.append({
            "title": data.title or "N/A",
            "company": data.company or "N/A",
            "location": data.location or "N/A",
            "url": data.link or "",
            "source": "LinkedIn",
            "date_posted": str(data.date) if data.date else "Recent",
        })

    def on_error(error):
        logger.error(f"LinkedIn error: {error}")

    def on_end():
        logger.info(f"LinkedIn done. {len(results)} results.")

    scraper = LinkedinScraper(
        chrome_executable_path=None,
        headless=True,
        max_workers=1,
        slow_mo=1.5,
        page_load_timeout=40,
    )

    if li_at:
        scraper.cookies = [{"name": "li_at", "value": li_at, "domain": ".linkedin.com"}]

    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)

    queries = []
    for keyword in KEYWORDS:
        for location in LOCATIONS:
            queries.append(
                Query(
                    query=keyword,
                    options=QueryOptions(
                        locations=[location],
                        apply_link=True,
                        limit=10,
                        filters=QueryFilters(
                            relevance=RelevanceFilters.RECENT,
                            time=TimeFilters.DAY,
                            type=[TypeFilters.INTERNSHIP, TypeFilters.FULL_TIME],
                            experience=[
                                ExperienceLevelFilters.INTERNSHIP,
                                ExperienceLevelFilters.ENTRY_LEVEL,
                            ],
                            on_site_or_remote=[
                                OnSiteOrRemoteFilters.REMOTE,
                                OnSiteOrRemoteFilters.HYBRID,
                            ],
                        ),
                    ),
                )
            )

    scraper.run(queries)
    return results
