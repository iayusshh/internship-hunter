# Internship Hunter v2

A daily automated pipeline that scrapes **11 job sources + Unstop Hackathons**, auto-applies via **Telegram-controlled bot**, generates AI cover letters, finds recruiter emails, and surfaces referral connections — all delivered to your phone every morning at **9 AM IST**.

---

## What It Does

| Layer | What happens |
|---|---|
| **Scrape** | 11 sources: LinkedIn, Indeed, Glassdoor, Internshala, Unstop, Naukri, YC Jobs, Wellfound, Turing, Mercor, HN "Who's Hiring" + Unstop Hackathons |
| **Filter** | Drops non-tech, scam listings, US-only, low stipend, senior roles. Hackathons ranked by prize & relevance |
| **Dedup** | URL hash + title\|company hash — 60-day window, persisted in `seen_jobs.json` |
| **Notify** | HTML email digest + individual Telegram cards with action buttons |
| **Act** | Tap a button → bot applies/registers, cold-emails, or finds your 2nd-degree connections |

Three job categories: **Internships** (India-focused, stipend-filtered), **Remote Full-Time** (salary-filtered, global), and **Hackathons** (prize-ranked, top 10 per digest).

---

## Telegram Control

Each job/hackathon arrives as its own card with buttons:

```
📚 Software Engineer Intern          🏆 ML Hackathon
🏢 Google                            🏢 Devfolio
📍 Bangalore, India                  📍 Online
💰 ₹50,000/month                     🏅 Prize: ₹1,00,000
LinkedIn · Internship                ⏰ Deadline: 2025-06-30

[🤖 Auto Apply]  [🔗 Open]          [🤖 Register]  [🔗 Open]
[📧 Cold Email]  [🤝 Referral]
```

| Button | What it does |
|---|---|
| **🤖 Auto Apply** | Runs Playwright, logs in, fills and submits the application. Updates to ✅ / ❌. |
| **🔗 Open** | Opens the job URL directly in your browser. |
| **📧 Cold Email** | Finds a recruiter email (Hunter.io or pattern), drafts a Claude-generated email, shows preview, sends on confirm. |
| **🤝 Referral** | Opens a LinkedIn 2nd-degree connection search for that company with a suggested outreach message. |

---

## Project Structure

```
internship-hunter/
├── main.py                      # Orchestrator — scraper registry + pipeline
├── config.json                  # All settings (edit via web UI or directly)
├── config_manager.py            # Config load/save + DEFAULT_CONFIG
├── job_filters.py               # Role, paid, quality, and remote filters
├── deduplicator.py              # URL + content-hash dedup (seen_jobs.json)
├── notifier.py                  # Email digest + Telegram job cards with buttons
├── telegram_bot.py              # Polling bot — handles all Telegram button taps
├── app.py                       # Flask web config panel (localhost:5000)
├── seen_jobs.json               # Dedup state — committed to persist across CI runs
├── applicant_profile.json       # YOUR profile: name, email, resume (gitignored)
│
├── scrapers/
│   ├── base.py                  # JobDict TypedDict
│   ├── jobspy_scraper.py        # LinkedIn + Indeed + Glassdoor (python-jobspy)
│   ├── internshala_scraper.py   # Internshala HTML scraper
│   ├── unstop_scraper.py        # Unstop JSON API
│   ├── naukri_scraper.py        # Naukri API + HTML fallback (fresher/intern)
│   ├── yc_scraper.py            # YC / Work at a Startup
│   ├── wellfound_scraper.py     # Wellfound Apollo state parse
│   ├── turing_scraper.py        # Turing remote jobs HTML
│   ├── mercor_scraper.py        # Mercor public JSON API
│   └── hn_scraper.py            # HackerNews "Who is Hiring?" (Algolia + Firebase)
│
├── autoapply/
│   ├── tracker.py               # SQLite: applications + outreach tables
│   ├── cover_letter.py          # Claude Haiku cover letter
│   ├── resume_tailor.py         # Resume-aware tailored cover letter
│   ├── base_applier.py          # Playwright ABC + human-delay helpers
│   ├── linkedin_applier.py      # LinkedIn Easy Apply automation
│   ├── indeed_applier.py        # Indeed Quick Apply automation
│   ├── internshala_applier.py   # Internshala apply automation
│   ├── naukri_applier.py        # Naukri apply automation
│   └── unstop_applier.py        # Unstop jobs + hackathon registration
│
├── outreach/
│   ├── cold_email.py            # Email finder + Claude draft + Gmail send
│   └── referral_finder.py       # LinkedIn search URL + optional Playwright scraper
│
├── templates/                   # Flask UI templates (+ applications, bot settings)
├── static/style.css
└── .github/workflows/
    └── daily_hunt.yml           # GitHub Actions cron (9 AM IST, 45 min timeout)
```

---

## One-Time Setup

### 1 — Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/internship-hunter.git
cd internship-hunter
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2 — Fill in your applicant profile

```bash
python -c "from autoapply import _load_profile; _load_profile()"
# Creates applicant_profile.json — fill it in
```

Open `applicant_profile.json` and fill in:
- `full_name`, `email`, `phone`
- `resume_path` — absolute path to your PDF resume
- `resume_text` — paste your full resume as plain text (used for AI tailoring)
- `bio`, `education`, `github_url`

### 3 — Gmail App Password

1. Google Account → Security → enable 2-Step Verification
2. Security → App passwords → name it `Internship Hunter`
3. Copy the 16-character password

### 4 — Telegram Bot

1. Message **@BotFather** → `/newbot` → follow prompts → save bot token
2. Start a chat with your bot
3. Get your Chat ID: open `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending the bot a message

### 5 — Add GitHub Secrets

Repo → Settings → Secrets and variables → Actions → New repository secret

| Secret | Value |
|---|---|
| `GMAIL_USER` | your Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char app password |
| `TELEGRAM_BOT_TOKEN` | bot token |
| `TELEGRAM_CHAT_ID` | your chat ID |
| `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD` | auto-apply on LinkedIn |
| `INDEED_EMAIL` / `INDEED_PASSWORD` | auto-apply on Indeed |
| `INTERNSHALA_EMAIL` / `INTERNSHALA_PASSWORD` | auto-apply on Internshala |
| `NAUKRI_EMAIL` / `NAUKRI_PASSWORD` | auto-apply on Naukri |
| `UNSTOP_EMAIL` / `UNSTOP_PASSWORD` | auto-apply/register on Unstop |
| `ANTHROPIC_API_KEY` | Claude API (cover letters + resume tailoring) |
| `HUNTER_API_KEY` | Hunter.io (optional, for cold email finding) |

### 6 — Set your email recipient and push

```bash
# Edit config.json → notifications.email_recipients → ["you@email.com"]
git add . && git commit -m "initial setup" && git push -u origin main
```

GitHub Actions runs automatically at **9:00 AM IST every day**.

---

## Running Locally

```bash
source .venv/bin/activate

# Copy and fill in secrets
cp .env.example .env
# edit .env

# Run the full pipeline
python main.py

# Start the Telegram bot (keep running to handle button taps)
python telegram_bot.py

# Start the web config panel
python app.py  # http://localhost:5000
```

Trigger manually on GitHub: Actions tab → **Daily Internship Hunter** → **Run workflow**.

---

## Telegram Bot Commands

| Command | What it does |
|---|---|
| `/start` | Shows bot status and all-time application stats |
| `/stats` | Application counts: applied / failed / skipped / queued |

---

## Local Web UI

```bash
python app.py   # http://localhost:5000
```

| Page | What you configure |
|---|---|
| Dashboard | Overview, filter toggles, source caps, run pipeline button |
| **Hackathons** | Top 10 Unstop hackathons ranked by prize — fetch on demand, register directly |
| Keywords & Locations | Search terms for all 11 sources |
| Role Filters | Tech include/exclude keywords, job type toggles, salary minimums |
| Block Lists | Blocked companies, dubious keywords, unpaid indicators |
| Source Caps | Max jobs per source per digest (incl. hackathon cap) |
| Location Rules | Indian city hints, US-only detection |
| Notifications | Email recipients, channel toggles |
| **Applications** | Full tracker table: every auto-apply attempt with status + cover letter |
| **Bot Settings** | Auto-apply toggles, platform selection, applicant profile editor, credential status |

---

## Configuration

All settings live in `config.json`. Key sections:

### `search`
Per-source keywords. `jobspy_internship_keywords` drives LinkedIn/Indeed/Glassdoor. `naukri_keywords` for Naukri. `hn_hiring_keywords` for filtering HN comments.

### `filters`
- `enable_internships` / `enable_full_time_remote` — toggle entire job categories
- `strict_paid_only` — drop internships with no stipend data
- `min_stipend_inr` — INR floor for Indian internships (default ₹5,000)
- `min_salary_usd_annual` — USD floor for full-time roles (default $40,000)
- `exclude_us_only` — drop roles requiring US work authorization

### `sources`
Per-source delivery caps. LinkedIn internships have a separate India/offshore split with `cap_linkedin_indian`, `cap_linkedin_offshore`, and `max_per_offshore_country`.

### `autoapply`
- `cover_letter_enabled` — generate AI cover letters
- `use_resume_tailor` — use full resume text for context (requires `ANTHROPIC_API_KEY`)
- `headless` — run browser invisibly (set false for debugging or 2FA)
- `platforms` — which platforms the bot applies to
- `max_per_day` — daily application cap

### `outreach`
- `cold_email_enabled` — show cold email button on all job cards
- `referral_finder_enabled` — show referral button on all job cards
- `referral_playwright` — actually scrape LinkedIn for contacts (vs URL-only mode)

### `dedup`
`expiry_days` (default 60) — a job disappears for this long after you first see it.

---

## How Deduplication Works

Every job is hashed two ways:
1. **URL hash** — normalized URL (tracking params stripped)
2. **Content hash** — MD5 of `title|company` (catches cross-source duplicates)

Both hashes stored in `seen_jobs.json` (committed to git) with a timestamp. Entries older than `expiry_days` are pruned automatically.

---

## How Auto-Apply Works

1. Daily pipeline sends each job as a Telegram card with buttons
2. You run `python telegram_bot.py` locally (keep it running)
3. Tap **🤖 Auto Apply** on any card
4. Bot opens Chromium, logs in to the platform, fills the application form using `applicant_profile.json`, generates a tailored cover letter with Claude, and submits
5. Button updates to ✅ Applied or ❌ reason
6. Application logged in `applications.db` with full cover letter

**Platforms supported**: LinkedIn Easy Apply, Indeed Quick Apply, Internshala, Naukri, Unstop (jobs + hackathon registration)

---

## How Cold Email Works

1. Tap **📧 Cold Email** on any job card
2. Bot finds a contact email: tries Hunter.io API first, then guesses `careers@/jobs@/hiring@{domain}`
3. Claude drafts a short personalized email using your bio and the role
4. Preview arrives in Telegram — tap **✅ Send** to send via Gmail or **❌ Skip**
5. Sent email tracked in `applications.db`

Set `HUNTER_API_KEY` for better email finding (25 free searches/month on Hunter.io free tier).

---

## Adding a New Scraper

1. Create `scrapers/your_scraper.py` — return `list[JobDict]` (see `scrapers/base.py`)
2. Set `job_type="internship"` or `"full_time_remote"` on every job
3. Register it in `SCRAPER_REGISTRY` in `main.py`
4. Add a cap key to `config.json → sources` and `config_manager.py → DEFAULT_CONFIG`
5. Wire the cap into `_apply_source_caps()` in `main.py`
6. Add a stepper field to `app.py → sources()` and `templates/sources.html`

---

## Known Limitations

- **LinkedIn bot detection**: Playwright in headless mode can be detected. Mitigations are in place (random delays, webdriver masking, one browser per application). If your account gets flagged, switch to `headless: false` and complete 2FA manually.
- **Indeed email verification**: If Indeed triggers an email challenge on login, the applier skips that session with a warning.
- **HN scraper**: Comments are free-form text; the parser handles the pipe-separated format well but verbose posts may not parse cleanly.
- **Naukri**: Uses an unofficial API and may return empty results if the endpoint is blocked. HTML fallback is attempted.
- **Wellfound**: DataDome bot-protection may block requests — returns `[]` and logs a warning.
- **Cold email domains**: Domain inference from company names is best-effort. Works well for single-word company names; less reliable for multi-word names.
- **Rate limits**: Each scraper has built-in delays (0.3–2s) to avoid bans.
