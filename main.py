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
from job_filters import filter_relevant_jobs
from notifier import send_email, send_telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

SOURCE_CAP_INTERNSHALA = int(os.environ.get("SOURCE_CAP_INTERNSHALA", "5"))
SOURCE_CAP_UNSTOP = int(os.environ.get("SOURCE_CAP_UNSTOP", "5"))


def _prioritize_sources(jobs: list[dict]) -> list[dict]:
    linkedin = [j for j in jobs if j.get("source") == "LinkedIn"]
    internshala = [j for j in jobs if j.get("source") == "Internshala"]
    unstop = [j for j in jobs if j.get("source") == "Unstop"]
    other = [j for j in jobs if j.get("source") not in {"LinkedIn", "Internshala", "Unstop"}]

    selected = []
    selected.extend(linkedin)  # Keep all good LinkedIn roles.
    selected.extend(internshala[:SOURCE_CAP_INTERNSHALA])
    selected.extend(unstop[:SOURCE_CAP_UNSTOP])
    selected.extend(other)
    return selected


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

    # Keep only paid, tech-focused internships (dev/devops/AI-ML/SE/SDE/SOE).
    relevant_jobs = filter_relevant_jobs(all_jobs)
    logger.info(f"Relevant jobs after role+paid filters: {len(relevant_jobs)}")

    # ── Deduplication ─────────────────────────
    new_jobs = filter_new_jobs(relevant_jobs)
    logger.info(f"New (unseen) jobs after deduplication: {len(new_jobs)}")

    selected_jobs = _prioritize_sources(new_jobs)
    logger.info(
        "Selected jobs for delivery: %s (LinkedIn prioritized, Internshala<=%s, Unstop<=%s)",
        len(selected_jobs),
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
