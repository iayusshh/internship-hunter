#!/usr/bin/env python3
"""
Internship Hunter — Daily digest pipeline
Scrapes LinkedIn, Internshala, and Unstop for fresh internships,
deduplicates, and sends results via Email + Telegram.
"""

import logging
import sys
import os

from scrapers.linkedin_scraper import scrape_linkedin
from scrapers.internshala_scraper import scrape_internshala
from scrapers.unstop_scraper import scrape_unstop
from deduplicator import filter_new_jobs
from job_filters import filter_relevant_jobs, quality_score
from notifier import send_email, send_telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

SOURCE_CAP_LINKEDIN_INDIAN = int(os.environ.get("SOURCE_CAP_LINKEDIN_INDIAN", "10"))
SOURCE_CAP_LINKEDIN_OFFSHORE = int(os.environ.get("SOURCE_CAP_LINKEDIN_OFFSHORE", "10"))
LINKEDIN_MAX_PER_OFFSHORE_COUNTRY = int(os.environ.get("LINKEDIN_MAX_PER_OFFSHORE_COUNTRY", "3"))
SOURCE_CAP_INTERNSHALA = int(os.environ.get("SOURCE_CAP_INTERNSHALA", "5"))
SOURCE_CAP_UNSTOP = int(os.environ.get("SOURCE_CAP_UNSTOP", "5"))

INDIAN_LOCATION_HINTS = [
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "mumbai",
    "delhi",
    "noida",
    "gurgaon",
    "chennai",
    "kolkata",
    "ahmedabad",
    "coimbatore",
    "kochi",
    "jaipur",
]


def _is_indian_listing(job: dict) -> bool:
    location = str(job.get("location", "")).lower()
    company = str(job.get("company", "")).lower()
    haystack = f"{location} {company}"
    return any(token in haystack for token in INDIAN_LOCATION_HINTS)


def _infer_country(job: dict) -> str:
    location = str(job.get("location", "")).lower().strip()
    if _is_indian_listing(job):
        return "India"

    country_aliases = {
        "united states": "United States",
        "usa": "United States",
        "u.s.": "United States",
        "canada": "Canada",
        "australia": "Australia",
        "new zealand": "New Zealand",
        "england": "United Kingdom",
        "united kingdom": "United Kingdom",
        "uk": "United Kingdom",
        "germany": "Germany",
        "netherlands": "Netherlands",
        "france": "France",
        "singapore": "Singapore",
        "uae": "UAE",
        "united arab emirates": "UAE",
        "indonesia": "Indonesia",
        "philippines": "Philippines",
        "vietnam": "Vietnam",
        "china": "China",
        "japan": "Japan",
        "south korea": "South Korea",
        "iran": "Iran",
        "europe": "Europe",
        "asia": "Asia",
        "middle east": "Middle East",
        "remote": "Remote",
        "worldwide": "Worldwide",
    }

    for alias, country in country_aliases.items():
        if alias in location:
            return country

    # Fallback: use trailing location segment if available (e.g., "Berlin, Germany").
    if "," in location:
        tail = location.split(",")[-1].strip()
        if tail:
            return tail.title()

    return "Other"


def _prioritize_sources(jobs: list[dict]) -> list[dict]:
    linkedin = [j for j in jobs if j.get("source") == "LinkedIn"]
    internshala = [j for j in jobs if j.get("source") == "Internshala"]
    unstop = [j for j in jobs if j.get("source") == "Unstop"]
    other = [j for j in jobs if j.get("source") not in {"LinkedIn", "Internshala", "Unstop"}]

    linkedin = sorted(linkedin, key=quality_score, reverse=True)
    linkedin_indian = [j for j in linkedin if _is_indian_listing(j)]
    linkedin_offshore = [j for j in linkedin if not _is_indian_listing(j)]

    selected = []
    selected.extend(linkedin_indian[:SOURCE_CAP_LINKEDIN_INDIAN])

    offshore_selected = []
    offshore_country_counts: dict[str, int] = {}
    for job in linkedin_offshore:
        if len(offshore_selected) >= SOURCE_CAP_LINKEDIN_OFFSHORE:
            break
        country = _infer_country(job)
        if offshore_country_counts.get(country, 0) >= LINKEDIN_MAX_PER_OFFSHORE_COUNTRY:
            continue
        offshore_country_counts[country] = offshore_country_counts.get(country, 0) + 1
        offshore_selected.append(job)

    selected.extend(offshore_selected)

    selected.extend(internshala[:SOURCE_CAP_INTERNSHALA])
    selected.extend(unstop[:SOURCE_CAP_UNSTOP])
    selected.extend(other)
    return selected


def _source_counts(jobs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for job in jobs:
        src = str(job.get("source", "Other"))
        counts[src] = counts.get(src, 0) + 1
    return counts


def main():
    logger.info("═══════════════════════════════════════")
    logger.info("  Internship Hunter — Starting Run")
    logger.info("═══════════════════════════════════════")

    all_jobs = []

    # ── LinkedIn ──────────────────────────────
    logger.info("Scraping LinkedIn...")
    try:
        linkedin_jobs = scrape_linkedin()
        logger.info(f"  LinkedIn: {len(linkedin_jobs)} raw results")
        all_jobs.extend(linkedin_jobs)
    except Exception as e:
        logger.error(f"  LinkedIn scraper failed: {e}")

    # ── Internshala ───────────────────────────
    logger.info("Scraping Internshala...")
    try:
        internshala_jobs = scrape_internshala()
        logger.info(f"  Internshala: {len(internshala_jobs)} raw results")
        all_jobs.extend(internshala_jobs)
    except Exception as e:
        logger.error(f"  Internshala scraper failed: {e}")

    # ── Unstop ────────────────────────────────
    logger.info("Scraping Unstop...")
    try:
        unstop_jobs = scrape_unstop()
        logger.info(f"  Unstop: {len(unstop_jobs)} raw results")
        all_jobs.extend(unstop_jobs)
    except Exception as e:
        logger.error(f"  Unstop scraper failed: {e}")

    logger.info(f"Total raw results: {len(all_jobs)}")
    logger.info(f"Raw by source: {_source_counts(all_jobs)}")

    # Keep only paid, tech-focused internships (dev/devops/AI-ML/SE/SDE/SOE).
    relevant_jobs = filter_relevant_jobs(all_jobs)
    logger.info(f"Relevant jobs after role+paid filters: {len(relevant_jobs)}")
    logger.info(f"Relevant by source: {_source_counts(relevant_jobs)}")

    # ── Deduplication ─────────────────────────
    new_jobs = filter_new_jobs(relevant_jobs)
    logger.info(f"New (unseen) jobs after deduplication: {len(new_jobs)}")
    logger.info(f"New by source: {_source_counts(new_jobs)}")

    selected_jobs = _prioritize_sources(new_jobs)
    logger.info(
        "Selected jobs for delivery: %s (LinkedIn India<=%s, LinkedIn offshore<=%s, max %s per offshore country, Internshala<=%s, Unstop<=%s)",
        len(selected_jobs),
        SOURCE_CAP_LINKEDIN_INDIAN,
        SOURCE_CAP_LINKEDIN_OFFSHORE,
        LINKEDIN_MAX_PER_OFFSHORE_COUNTRY,
        SOURCE_CAP_INTERNSHALA,
        SOURCE_CAP_UNSTOP,
    )

    # ── Notify ────────────────────────────────
    if not selected_jobs:
        logger.info("No new jobs to send. Sending empty digest anyway.")

    logger.info("Sending email...")
    try:
        send_email(selected_jobs)
        logger.info("  Email sent ✓")
    except Exception as e:
        logger.error(f"  Email failed: {e}")

    logger.info("Sending Telegram message...")
    try:
        send_telegram(selected_jobs)
        logger.info("  Telegram sent ✓")
    except Exception as e:
        logger.error(f"  Telegram failed: {e}")

    logger.info("═══════════════════════════════════════")
    logger.info(f"  Done. {len(selected_jobs)} new internship(s) delivered.")
    logger.info("═══════════════════════════════════════")


if __name__ == "__main__":
    main()
