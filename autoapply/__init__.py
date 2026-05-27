"""
Auto-apply orchestrator.
Called from main.py after the daily digest is sent.
"""

import json
import logging
import os
import random
import time

from config_manager import load_config
from . import tracker
from .cover_letter      import generate_cover_letter
from .linkedin_applier  import LinkedInApplier
from .indeed_applier    import IndeedApplier
from .internshala_applier import InternshalaApplier

logger = logging.getLogger(__name__)

_PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "applicant_profile.json")

_DEFAULT_PROFILE = {
    "full_name":         "",
    "email":             "",
    "phone":             "",
    "linkedin_url":      "",
    "github_url":        "",
    "portfolio_url":     "",
    "resume_path":       "",
    "resume_text":       "",   # full resume as plain text — used by resume_tailor.py
    "years_experience":  0,
    "education":         "",
    "bio":               "",
    "notice_period":     "Immediate",
    "expected_stipend":  "",
    "common_answers": {
        "why_this_role":       "",
        "strengths":           "",
        "availability":        "Immediate",
        "willing_to_relocate": False,
    },
}

_PLATFORM_MAP = {
    "LinkedIn":    LinkedInApplier,
    "Indeed":      IndeedApplier,
    "Internshala": InternshalaApplier,
}


def _load_profile() -> dict | None:
    if not os.path.exists(_PROFILE_PATH):
        with open(_PROFILE_PATH, "w") as f:
            json.dump(_DEFAULT_PROFILE, f, indent=2)
        logger.warning(
            "autoapply: applicant_profile.json was missing — created template at %s. "
            "Fill it in and re-run to enable auto-apply.",
            _PROFILE_PATH,
        )
        return None

    with open(_PROFILE_PATH) as f:
        profile = json.load(f)

    if not profile.get("full_name") or not profile.get("email"):
        logger.warning("autoapply: applicant_profile.json is not configured (full_name/email empty) — skipping")
        return None

    return profile


def run_autoapply(jobs: list[dict]) -> None:
    cfg = load_config().get("autoapply", {})
    if not cfg.get("enabled", False):
        return

    profile = _load_profile()
    if not profile:
        return

    tracker.init_db()
    daily_limit     = int(cfg.get("max_per_day", 20))
    applied_today   = tracker.count_applied_today()
    enabled_platforms = [p.lower() for p in cfg.get("platforms", ["linkedin", "indeed", "internshala"])]
    headless        = bool(cfg.get("headless", True))
    cover_letter_on = bool(cfg.get("cover_letter_enabled", True))

    logger.info(
        "autoapply: starting — %d jobs to consider, %d applied today (limit %d)",
        len(jobs), applied_today, daily_limit,
    )

    for job in jobs:
        if applied_today >= daily_limit:
            logger.info("autoapply: daily limit (%d) reached — stopping", daily_limit)
            break

        source = str(job.get("source", ""))
        ApplierClass = _PLATFORM_MAP.get(source)
        if ApplierClass is None:
            continue  # YC / Wellfound / Turing / Mercor — non-standard forms, skip
        if source.lower() not in enabled_platforms:
            continue
        if tracker.already_applied(str(job.get("url", ""))):
            continue

        app_id = tracker.add_job(job)

        # Generate cover letter
        cover_letter = ""
        if cover_letter_on:
            try:
                cover_letter = generate_cover_letter(
                    str(job.get("title", "")),
                    str(job.get("company", "")),
                    str(job.get("description", "")),
                    profile,
                )
            except Exception as e:
                logger.warning("autoapply: cover letter failed for %s — %s", job.get("title"), e)

        # Apply via platform
        applier = ApplierClass(profile, headless=headless)
        try:
            tracker.update_status(app_id, "applying")
            applier.start()

            if not applier.login():
                tracker.update_status(app_id, "failed", error_msg="login_failed")
                logger.warning(
                    "autoapply: login failed for %s — skipping remaining %s jobs",
                    source, source,
                )
                # Don't try more jobs from this platform in this run
                enabled_platforms = [p for p in enabled_platforms if p != source.lower()]
                continue

            success, error = applier.apply(job, cover_letter)
            status = "applied" if success else "failed"
            tracker.update_status(app_id, status, error_msg=error or None, cover_letter=cover_letter or None)

            if success:
                applied_today += 1
                logger.info(
                    "autoapply: applied — %s @ %s via %s",
                    job.get("title"), job.get("company"), source,
                )
            else:
                logger.warning(
                    "autoapply: failed — %s @ %s — %s",
                    job.get("title"), job.get("company"), error,
                )

        except Exception as e:
            tracker.update_status(app_id, "failed", error_msg=str(e))
            logger.error("autoapply: exception for %s — %s", job.get("url"), e)
        finally:
            applier.stop()
            time.sleep(random.uniform(3, 8))

    logger.info(
        "autoapply: done — %d applied today total",
        tracker.count_applied_today(),
    )
