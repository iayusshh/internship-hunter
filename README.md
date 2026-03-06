# 🎯 Internship Hunter

A daily automated pipeline that scrapes **LinkedIn**, **Internshala**, and **Unstop** for remote/hybrid internships and delivers a digest to your **Email** and **Telegram** every morning at **9 AM IST**.

---

## 📁 Project Structure

```
internship-hunter/
├── main.py                         # Orchestrator — runs everything
├── deduplicator.py                 # Filters already-seen jobs
├── notifier.py                     # Email + Telegram delivery
├── requirements.txt
├── scrapers/
│   ├── linkedin_scraper.py
│   ├── internshala_scraper.py
│   └── unstop_scraper.py
└── .github/
    └── workflows/
        └── daily_hunt.yml          # GitHub Actions cron job
```

---

## 🚀 One-Time Setup

### Step 1 — Create a GitHub Repository

```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/internship-hunter.git
```

---

### Step 2 — Gmail App Password

Gmail doesn't allow sending emails with your normal password. You need an **App Password**.

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Go to **Security → App passwords**
4. Select app: `Mail`, device: `Other (custom name)` → type `Internship Hunter`
5. Copy the 16-character password shown

---

### Step 3 — Telegram Bot Setup

1. Open Telegram → search **@BotFather**
2. Send `/newbot` → follow prompts → give it any name (e.g. `InternshipHunterBot`)
3. BotFather gives you a **token** like `7312345678:AAFxyz...` — save this
4. Start a chat with your new bot (search its username, click Start)
5. Get your **Chat ID**: visit this URL in your browser (replace `<TOKEN>` with your bot token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   After sending your bot a message, you'll see a JSON response. Find `"chat":{"id":XXXXXXX}` — that number is your Chat ID.

---

### Step 4 — LinkedIn Cookie (`li_at`)

This lets the LinkedIn scraper work without being blocked immediately.

1. Log into LinkedIn in Chrome
2. Open DevTools → Application → Cookies → `https://www.linkedin.com`
3. Find the cookie named `li_at` — copy its **Value**

> ⚠️ This cookie expires periodically. If LinkedIn results stop working, refresh this secret.

---

### Step 5 — Add GitHub Secrets

Go to your repo on GitHub → **Settings → Secrets and variables → Actions → New repository secret**

Add these 5 secrets:

| Secret Name          | Value                              |
|----------------------|------------------------------------|
| `GMAIL_USER`         | your Gmail address                 |
| `GMAIL_APP_PASSWORD` | the 16-char app password           |
| `TELEGRAM_BOT_TOKEN` | your bot token from BotFather      |
| `TELEGRAM_CHAT_ID`   | your chat ID number                |
| `LI_AT_COOKIE`       | your LinkedIn `li_at` cookie value |

---

### Step 6 — Push to GitHub

```bash
git add .
git commit -m "initial commit"
git push -u origin main
```

GitHub Actions will now run automatically at **9:00 AM IST every day**.

---

## 🧪 Manual Test Run

You can trigger it manually anytime:

1. Go to your repo → **Actions** tab
2. Click **Daily Internship Hunter** → **Run workflow** → **Run workflow**

Or run locally:

```bash
pip install -r requirements.txt

# Set env variables
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export TELEGRAM_BOT_TOKEN="7312345678:AAFxyz..."
export TELEGRAM_CHAT_ID="123456789"
export LI_AT_COOKIE="your_li_at_value"
export STRICT_PAID_ONLY="true"
export MIN_STIPEND_INR="5000"
export SOURCE_CAP_INTERNSHALA="5"
export SOURCE_CAP_UNSTOP="5"
export SOURCE_CAP_LINKEDIN="40"
export LINKEDIN_MAX_PAGES="1"
export LINKEDIN_MIN_QUALITY="6"

python main.py
```

`STRICT_PAID_ONLY=true` drops listings without clear stipend data.
`MIN_STIPEND_INR=5000` removes very low-paying internships (for INR listings).
`SOURCE_CAP_INTERNSHALA=5` and `SOURCE_CAP_UNSTOP=5` keep non-LinkedIn noise low.
`SOURCE_CAP_LINKEDIN=40` limits delivery to top-ranked LinkedIn matches.
`LINKEDIN_MAX_PAGES=1` keeps scrape breadth focused.
`LINKEDIN_MIN_QUALITY=6` keeps only stronger LinkedIn matches.

---

## ⚙️ Customizing Keywords

Edit `KEYWORDS` in `scrapers/linkedin_scraper.py` and `SEARCH_TERMS` in `scrapers/internshala_scraper.py` to add/remove search terms.

---

## 🧹 Deduplication

Seen jobs are stored in `seen_jobs.json` (persisted via GitHub Actions cache between runs). Jobs older than **30 days** are automatically pruned from the log so you'll see them again if still active.

---

## ⚠️ Known Limitations

- **LinkedIn**: May require refreshing `li_at` cookie every few weeks as it expires
- **Internshala**: HTML structure may change; if results drop, the selectors in `internshala_scraper.py` may need updating
- **Unstop**: Uses their public API; may need parameter updates if their API changes
- **Rate limits**: Built-in `1.5s` delays between requests to avoid bans
