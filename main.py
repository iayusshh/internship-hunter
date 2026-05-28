#!/usr/bin/env python3
"""
Internship Hunter v2 — Daily digest pipeline
Scrapes 9 sources for internships and remote full-time jobs,
deduplicates, and delivers via Email + Telegram.
"""

import logging
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scrapers.jobspy_scraper    import scrape_jobspy_internships, scrape_jobspy_fulltime_remote
from scrapers.internshala_scraper import scrape_internshala
from scrapers.unstop_scraper    import scrape_unstop, scrape_unstop_hackathons
from scrapers.yc_scraper        import scrape_yc
from scrapers.wellfound_scraper import scrape_wellfound
from scrapers.turing_scraper    import scrape_turing
from scrapers.mercor_scraper    import scrape_mercor
from scrapers.naukri_scraper    import scrape_naukri
from scrapers.hn_scraper        import scrape_hn

from deduplicator import filter_new_jobs
from job_filters  import filter_relevant_jobs, quality_score, hackathon_quality_score
from notifier     import send_email, send_telegram
from config_manager import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

SCRAPER_REGISTRY = [
    ("LinkedIn/Indeed/Glassdoor (Internships)", scrape_jobspy_internships),
    ("LinkedIn/Indeed/Glassdoor (Full-Time)",   scrape_jobspy_fulltime_remote),
    ("Internshala",                             scrape_internshala),
    ("Unstop",                                  scrape_unstop),
    ("Unstop Hackathons",                       scrape_unstop_hackathons),
    ("Naukri",                                  scrape_naukri),
    ("YC Jobs",                                 scrape_yc),
    ("Wellfound",                               scrape_wellfound),
    ("Turing",                                  scrape_turing),
    ("Mercor",                                  scrape_mercor),
    ("HN Jobs",                                 scrape_hn),
]


def _source_counts(jobs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for job in jobs:
        src = str(job.get("source", "Other"))
        counts[src] = counts.get(src, 0) + 1
    return counts


def _get_indian_hints() -> list[str]:
    return load_config()["locations"]["indian_hints"]


def _is_indian_listing(job: dict) -> bool:
    haystack = _normalize(f"{job.get('location', '')} {job.get('company', '')}")
    return any(token in haystack for token in _get_indian_hints())


def _normalize(text: str) -> str:
    return (text or "").lower().strip()


def _infer_country(job: dict) -> str:
    location = _normalize(str(job.get("location", "")))
    if _is_indian_listing(job):
        return "India"
    country_aliases = {
        "united states": "United States", "usa": "United States", "u.s.": "United States",
        "canada": "Canada", "australia": "Australia", "new zealand": "New Zealand",
        "england": "United Kingdom", "united kingdom": "United Kingdom", "uk": "United Kingdom",
        "germany": "Germany", "netherlands": "Netherlands", "france": "France",
        "singapore": "Singapore", "uae": "UAE", "united arab emirates": "UAE",
        "indonesia": "Indonesia", "philippines": "Philippines", "vietnam": "Vietnam",
        "china": "China", "japan": "Japan", "south korea": "South Korea",
        "iran": "Iran", "europe": "Europe", "asia": "Asia",
        "middle east": "Middle East", "remote": "Remote", "worldwide": "Worldwide",
    }
    for alias, country in country_aliases.items():
        if alias in location:
            return country
    if "," in location:
        tail = location.split(",")[-1].strip()
        if tail:
            return tail.title()
    return "Other"


def _apply_source_caps(jobs: list[dict]) -> list[dict]:
    cfg  = load_config()["sources"]

    # Per-source cap lookup: (source_name, job_type) → config key
    cap_map: dict[tuple[str, str], int] = {
        ("LinkedIn",  "internship"):        cfg.get("cap_linkedin_indian", 10) + cfg.get("cap_linkedin_offshore", 10),
        ("Indeed",    "internship"):        cfg.get("cap_indeed_internship", 8),
        ("Glassdoor", "internship"):        cfg.get("cap_glassdoor_internship", 8),
        ("LinkedIn",  "full_time_remote"):  cfg.get("cap_linkedin_fulltime", 8),
        ("Indeed",    "full_time_remote"):  cfg.get("cap_indeed_fulltime", 8),
        ("Glassdoor", "full_time_remote"):  cfg.get("cap_glassdoor_fulltime", 8),
        ("Internshala", "internship"):      cfg.get("cap_internshala", 5),
        ("Unstop",    "internship"):          cfg.get("cap_unstop", 5),
        ("Unstop Hackathons", "hackathon"): cfg.get("cap_unstop_hackathon", 5),
        ("Naukri",    "internship"):         cfg.get("cap_naukri", 8),
        ("HN Jobs",   "internship"):        cfg.get("cap_hn", 8),
        ("HN Jobs",   "full_time_remote"):  cfg.get("cap_hn", 8),
        ("YC Jobs",   "internship"):        cfg.get("cap_yc", 10),
        ("YC Jobs",   "full_time_remote"):  cfg.get("cap_yc", 10),
        ("Wellfound", "internship"):        cfg.get("cap_wellfound", 10),
        ("Wellfound", "full_time_remote"):  cfg.get("cap_wellfound", 10),
        ("Turing",    "full_time_remote"):  cfg.get("cap_turing", 8),
        ("Mercor",    "full_time_remote"):  cfg.get("cap_mercor", 8),
    }

    # Hackathons: sort by quality so the cap keeps the best ones
    hackathon_jobs = sorted(
        [j for j in jobs if j.get("job_type") == "hackathon"],
        key=hackathon_quality_score,
        reverse=True,
    )
    non_hackathon_jobs = [j for j in jobs if j.get("job_type") != "hackathon"]
    jobs = hackathon_jobs + non_hackathon_jobs

    # LinkedIn internship: special India/offshore split
    linkedin_intern = [j for j in jobs if j.get("source") == "LinkedIn" and j.get("job_type") != "full_time_remote"]
    linkedin_intern = sorted(linkedin_intern, key=quality_score, reverse=True)
    cap_indian   = cfg.get("cap_linkedin_indian", 10)
    cap_offshore = cfg.get("cap_linkedin_offshore", 10)
    max_per_country = cfg.get("max_per_offshore_country", 3)

    li_indian   = [j for j in linkedin_intern if _is_indian_listing(j)][:cap_indian]
    li_offshore_raw = [j for j in linkedin_intern if not _is_indian_listing(j)]
    li_offshore: list[dict] = []
    country_counts: dict[str, int] = {}
    for job in li_offshore_raw:
        if len(li_offshore) >= cap_offshore:
            break
        c = _infer_country(job)
        if country_counts.get(c, 0) >= max_per_country:
            continue
        country_counts[c] = country_counts.get(c, 0) + 1
        li_offshore.append(job)

    selected: list[dict] = list(li_indian) + list(li_offshore)

    # All other sources: simple cap
    per_source_counts: dict[tuple[str, str], int] = {}
    for job in jobs:
        src   = str(job.get("source", ""))
        jtype = str(job.get("job_type", "internship"))

        # Skip LinkedIn internships (already handled above)
        if src == "LinkedIn" and jtype != "full_time_remote":
            continue

        key = (src, jtype)
        cap = cap_map.get(key, 99)
        count = per_source_counts.get(key, 0)
        if count < cap:
            selected.append(job)
            per_source_counts[key] = count + 1

    return selected


def main():
    logger.info("═══════════════════════════════════════════")
    logger.info("  Internship Hunter v2 — Starting Run")
    logger.info("═══════════════════════════════════════════")

    all_jobs: list[dict] = []

    for name, scraper_fn in SCRAPER_REGISTRY:
        logger.info(f"Scraping {name}...")
        try:
            jobs = scraper_fn()
            logger.info(f"  {name}: {len(jobs)} raw results")
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error(f"  {name} scraper failed: {e}")

    logger.info(f"Total raw: {len(all_jobs)} — by source: {_source_counts(all_jobs)}")

    relevant = filter_relevant_jobs(all_jobs)
    logger.info(f"After filters: {len(relevant)} — by source: {_source_counts(relevant)}")

    new_jobs = filter_new_jobs(relevant)
    logger.info(f"After dedup: {len(new_jobs)} — by source: {_source_counts(new_jobs)}")

    selected = _apply_source_caps(new_jobs)
    logger.info(f"After caps: {len(selected)} — by source: {_source_counts(selected)}")

    internships = [j for j in selected if j.get("job_type") != "full_time_remote"]
    fulltime    = [j for j in selected if j.get("job_type") == "full_time_remote"]
    logger.info(f"Breakdown: {len(internships)} internship(s), {len(fulltime)} remote full-time")

    # Persist last-run jobs so the dashboard Jobs page can display them
    try:
        import json as _json, time as _time
        _cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_run_jobs.json")
        with open(_cache_path, "w") as _f:
            _json.dump({"fetched_at": _time.time(), "jobs": selected}, _f, default=str)
    except Exception as e:
        logger.warning(f"Could not save jobs cache: {e}")

    logger.info("Sending email...")
    try:
        send_email(selected)
        logger.info("  Email sent ✓")
    except Exception as e:
        logger.error(f"  Email failed: {e}")

    logger.info("Sending Telegram...")
    try:
        send_telegram(selected)
        logger.info("  Telegram sent ✓")
    except Exception as e:
        logger.error(f"  Telegram failed: {e}")

    logger.info("═══════════════════════════════════════════")
    logger.info(f"  Done. {len(selected)} job(s) delivered ({len(internships)} intern + {len(fulltime)} full-time).")
    logger.info("═══════════════════════════════════════════")


if __name__ == "__main__":
    main()
