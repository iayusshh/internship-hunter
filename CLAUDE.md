# Internship Hunter — Claude Code Context

## What This Project Is

A daily automated job scraper + auto-apply pipeline. Scrapes **11 sources** for tech internships and remote full-time jobs, filters, deduplicates, and delivers via email + interactive Telegram at 9 AM IST via GitHub Actions. Includes an on-demand auto-apply bot controlled entirely through Telegram buttons.

---

## Architecture

```
main.py  →  SCRAPER_REGISTRY (11 scrapers)
         →  filter_relevant_jobs()   job_filters.py
         →  filter_new_jobs()        deduplicator.py
         →  _apply_source_caps()     main.py
         →  send_email()             notifier.py  (HTML digest)
         →  send_telegram()          notifier.py  (interactive job cards with buttons)

telegram_bot.py  →  polling bot (run locally)
                 →  handle_apply()         → autoapply/ appliers
                 →  handle_cold_email()    → outreach/cold_email.py
                 →  handle_find_referral() → outreach/referral_finder.py
                 →  handle_send_outreach() → outreach/cold_email.py + tracker.py
```

**Job model**: every job carries `job_type: "internship" | "full_time_remote"` — this drives all filtering, capping, and notification logic.

---

## Key Files

| File | Role |
|---|---|
| `main.py` | Orchestrator. `SCRAPER_REGISTRY` list drives which scrapers run. `_apply_source_caps()` applies per-source limits. |
| `scrapers/base.py` | `JobDict` TypedDict — the shared schema every scraper must return. |
| `scrapers/jobspy_scraper.py` | Wraps `python-jobspy` for LinkedIn, Indeed, Glassdoor. |
| `scrapers/naukri_scraper.py` | Naukri unofficial JSON API + HTML fallback. Fresher/intern roles in India. |
| `scrapers/hn_scraper.py` | HN "Who is Hiring?" thread via Algolia + Firebase APIs. Filters by keyword. |
| `config_manager.py` | `DEFAULT_CONFIG` is the source of truth. `load_config()` uses `_deep_merge` — new keys never break old `config.json`. |
| `job_filters.py` | `filter_relevant_jobs()` — internship path: tech role, paid, US-only, quality score. Full-time path: tech role, remote hint, salary. |
| `deduplicator.py` | URL hash + content hash (title\|company). Stores in `seen_jobs.json`. Do not refactor. |
| `notifier.py` | Email: two-section HTML digest. Telegram: individual job cards with inline keyboard buttons. |
| `app.py` | Flask web UI on port 5000. All routes read/write `config.json`. |
| `telegram_bot.py` | Polling bot. Run locally to handle button taps. Handles apply, cold email, referral. |

### autoapply/

| File | Role |
|---|---|
| `__init__.py` | `run_autoapply()` — batch orchestrator (available but not called from main.py). |
| `tracker.py` | SQLite DB (`applications.db`). Tables: `applications` + `outreach`. |
| `cover_letter.py` | Basic Claude Haiku cover letter. Falls back to template without API key. |
| `resume_tailor.py` | Enhanced cover letter using full `resume_text` from profile. |
| `base_applier.py` | `BasePlatformApplier` ABC + Playwright setup + human-delay helpers. |
| `linkedin_applier.py` | LinkedIn Easy Apply — login, multi-step modal, Q&A filler. |
| `indeed_applier.py` | Indeed Quick Apply — login, form fill, submit. |
| `internshala_applier.py` | Internshala — login, Apply Now, cover letter field. |

### outreach/

| File | Role |
|---|---|
| `cold_email.py` | Email finder (Hunter.io → pattern guess), Claude draft, Gmail SMTP send. |
| `referral_finder.py` | LinkedIn 2nd-degree search URL generator. Optional Playwright scraper. |

---

## Config

All settings in `config.json`. Edit via `python app.py` or directly.
When adding new config keys, also add to `DEFAULT_CONFIG` in `config_manager.py`.

Key config sections: `search`, `filters`, `sources`, `locations`, `notifications`, `autoapply`, `outreach`, `dedup`.

---

## Adding a New Scraper

1. Create `scrapers/your_scraper.py` — return `list[JobDict]`
2. Set `job_type` on every job (`"internship"` or `"full_time_remote"`)
3. Add to `SCRAPER_REGISTRY` in `main.py`
4. Add cap key to `DEFAULT_CONFIG["sources"]` in `config_manager.py`
5. Wire cap into `_apply_source_caps()` in `main.py`
6. Add form field to `app.py → sources()` route and `templates/sources.html`

---

## Common Tasks

```bash
# Run pipeline
source .venv/bin/activate && python main.py

# Run Telegram bot (keep running to handle button taps)
python telegram_bot.py

# Config web UI
python app.py   # http://localhost:5000

# Install deps
pip install -r requirements.txt && playwright install chromium
```

---

## Secrets (environment variables — never commit)

| Variable | Purpose |
|---|---|
| `GMAIL_USER` | Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char App Password |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat ID |
| `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD` | Auto-apply |
| `INDEED_EMAIL` / `INDEED_PASSWORD` | Auto-apply |
| `INTERNSHALA_EMAIL` / `INTERNSHALA_PASSWORD` | Auto-apply |
| `ANTHROPIC_API_KEY` | Cover letters + resume tailoring |
| `HUNTER_API_KEY` | Email finding for cold outreach (optional) |

---

## Applicant Profile (`applicant_profile.json`)

Gitignored. Created automatically on first bot run. Fill in:
- `full_name`, `email`, `phone` — form fields
- `resume_path` — PDF path for upload
- `resume_text` — full resume as plain text (used by `resume_tailor.py` for Claude context)
- `bio`, `education`, `github_url` — cover letter context
- `common_answers.availability` — "Immediately" / date string

---

## CI/CD

GitHub Actions at 3:30 AM UTC (9:00 AM IST). Timeout: 45 min.
Commits `seen_jobs.json` after each run to persist dedup state.
Playwright Chromium installed via `playwright install chromium --with-deps` step.

---

## Known Gotchas

- `"0/month"` in paid_blocklist must stay as word-boundary regex in `_is_paid_text()` — plain `in` matching would false-positive on "15000/month".
- `load_config()` deep-merges DEFAULT_CONFIG with on-disk values. New keys always have defaults. Test after adding to DEFAULT_CONFIG.
- `deduplicator.py` is stable — don't refactor without a bug to fix.
- jobspy returns a pandas DataFrame with NaN values — always use `.get()` or null checks when reading columns.
- The Telegram job card format (emoji prefix + company on line 2) is parsed by `telegram_bot._parse_job_card()` — keep `_fmt_job_card()` in `notifier.py` in sync with that parser.
- `autoapply/tracker.py` runs `init_db()` which is idempotent — safe to call multiple times (uses `CREATE TABLE IF NOT EXISTS`).
- LinkedIn Easy Apply forms vary per company (1–5 steps, custom questions). Unknown required fields fill with profile values or "N/A" and log a warning — they do not crash the bot.
