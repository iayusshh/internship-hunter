import os
import logging
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData, EventMetrics
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

FALLBACK_KEYWORDS = [
    "software engineer internship",
    "sde intern",
    "backend developer intern",
    "frontend developer intern",
    "full stack developer intern",
    "devops intern",
    "machine learning intern",
    "ai engineer intern",
]

LOCATIONS = ["India", "Worldwide"]


def _build_queries(keywords: list[str], strict: bool) -> list[Query]:
    queries = []
    for keyword in keywords:
        for location in LOCATIONS:
            filters = QueryFilters(
                relevance=RelevanceFilters.RECENT,
                time=TimeFilters.WEEK if strict else TimeFilters.MONTH,
                on_site_or_remote=[
                    OnSiteOrRemoteFilters.ON_SITE,
                    OnSiteOrRemoteFilters.REMOTE,
                    OnSiteOrRemoteFilters.HYBRID,
                ],
            )

            if strict:
                filters.type = [TypeFilters.INTERNSHIP]
                filters.experience = [
                    ExperienceLevelFilters.INTERNSHIP,
                    ExperienceLevelFilters.ENTRY_LEVEL,
                ]

            queries.append(
                Query(
                    query=keyword,
                    options=QueryOptions(
                        locations=[location],
                        apply_link=False,
                        skip_promoted_jobs=True,
                        limit=12 if strict else 16,
                        filters=filters,
                    ),
                )
            )
    return queries


def scrape_linkedin() -> list[dict]:
    results = []
    seen_urls = set()
    li_at = os.environ.get("LI_AT_COOKIE", "")

    def on_data(data: EventData):
        url = data.link or ""
        if not url or url in seen_urls:
            return
        seen_urls.add(url)

        results.append({
            "title": data.title or "N/A",
            "company": data.company or "N/A",
            "location": getattr(data, "location", None) or getattr(data, "place", None) or "N/A",
            "url": url,
            "source": "LinkedIn",
            "date_posted": str(data.date) if data.date else "Recent",
        })

    def on_metrics(metrics: EventMetrics):
        logger.info(f"LinkedIn metrics: {metrics}")

    def on_error(error):
        logger.error(f"LinkedIn error: {error}")

    def on_end():
        logger.info(f"LinkedIn done. {len(results)} results.")

    if not li_at:
        logger.warning("LI_AT_COOKIE is missing. LinkedIn may return 0 jobs in anonymous mode.")

    scraper = LinkedinScraper(
        chrome_executable_path=None,
        headless=True,
        max_workers=1,
        slow_mo=2.0,
        page_load_timeout=40,
    )

    if li_at:
        scraper.cookies = [{"name": "li_at", "value": li_at, "domain": ".linkedin.com"}]

    scraper.on(Events.DATA, on_data)
    scraper.on(Events.METRICS, on_metrics)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)

    strict_queries = _build_queries(KEYWORDS, strict=True)
    try:
        scraper.run(strict_queries)
    except Exception as error:
        logger.error(f"LinkedIn strict pass failed: {error}")

    # Fallback if strict pass under-delivers.
    if len(results) < 8:
        logger.info("LinkedIn strict pass returned few jobs; running relaxed fallback queries.")
        fallback_queries = _build_queries(FALLBACK_KEYWORDS, strict=False)
        try:
            scraper.run(fallback_queries)
        except Exception as error:
            logger.error(f"LinkedIn fallback pass failed: {error}")

    return results
