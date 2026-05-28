"""
Central configuration manager.
All hardcoded lists and env-var defaults live here and in config.json.
Secrets (Gmail, Telegram credentials) stay as environment variables only.
"""

import json
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")

DEFAULT_CONFIG: dict = {
    "search": {
        # jobspy covers LinkedIn, Indeed, Glassdoor
        "jobspy_internship_keywords": [
            "software engineer intern",
            "sde intern",
            "ml intern",
            "machine learning intern",
            "devops intern",
            "backend intern",
            "frontend intern",
            "data engineer intern",
            "data science intern",
            "ai intern",
            "full stack intern",
            "web developer intern",
            "android intern",
            "ios intern",
            "qa engineer intern",
            "site reliability intern",
        ],
        "jobspy_fulltime_keywords": [
            "software engineer remote",
            "backend engineer remote",
            "frontend engineer remote",
            "ml engineer remote",
            "machine learning engineer remote",
            "devops engineer remote",
            "full stack engineer remote",
            "data engineer remote",
            "sre remote",
        ],
        "jobspy_country_indeed": "worldwide",
        "jobspy_hours_old": 26,
        "jobspy_results_per_call": 15,

        # Internshala: URL slugs
        "internshala_terms": [
            "software-engineer",
            "full-stack-developer",
            "web-developer",
            "frontend-developer",
            "backend-developer",
            "artificial-intelligence",
            "machine-learning",
        ],

        # Unstop: free-text search
        "unstop_keywords": [
            "software engineer",
            "full stack",
            "developer",
            "frontend",
            "backend",
            "artificial intelligence",
            "machine learning",
        ],

        # Unstop hackathons: search terms
        "unstop_hackathon_keywords": [
            "machine learning",
            "web development",
            "data science",
            "software",
            "ai",
            "open innovation",
            "blockchain",
        ],

        # YC / Work at a Startup: role slugs
        "yc_roles": [
            "software_engineer",
            "machine_learning",
        ],

        # Wellfound: role slugs in URL
        "wellfound_roles": [
            "software-engineer",
            "backend-engineer",
            "machine-learning-engineer",
            "full-stack-engineer",
        ],

        # Mercor: free-text search
        "mercor_keywords": [
            "software engineer",
            "backend engineer",
            "machine learning",
            "full stack developer",
        ],

        # Naukri: search keywords (Indian fresher/internship roles)
        "naukri_keywords": [
            "software engineer intern",
            "sde intern",
            "developer intern",
            "full stack intern",
            "machine learning intern",
        ],

        # HackerNews "Who is Hiring?" — filter keywords
        "hn_hiring_keywords": [
            "python", "javascript", "typescript", "react", "node",
            "backend", "frontend", "full stack", "ml", "machine learning",
            "intern", "remote", "software engineer", "developer",
        ],
        "hn_results_cap": 20,

        # Turing: full category page URLs (only verified-live pages)
        "turing_urls": [
            "https://www.turing.com/jobs/remote-software-engineer-jobs",
            "https://www.turing.com/jobs/remote-full-stack-jobs",
            "https://www.turing.com/jobs/remote-frontend-developer-jobs",
            "https://www.turing.com/remote-developer-jobs",
        ],
    },

    "filters": {
        # Job type toggles
        "enable_internships":          True,
        "enable_full_time_remote":     True,

        # Full-time remote filters
        "min_salary_usd_annual":       40000,
        "full_time_require_remote_hint": True,
        "full_time_min_quality":       4,

        # Tech role keywords (shared across job types)
        "tech_include_keywords": [
            "software engineer",
            "software developer",
            "sde",
            "soe",
            "full stack",
            "frontend",
            "front end",
            "backend",
            "back end",
            "web developer",
            "app developer",
            "mobile developer",
            "android",
            "ios",
            "devops",
            "site reliability",
            "sre",
            "platform engineer",
            "machine learning",
            "ml",
            "ai",
            "artificial intelligence",
            "data science",
            "data engineer",
            "qa engineer",
            "test engineer",
            "software testing",
        ],
        "tech_exclude_keywords": [
            "business",
            "fundraising",
            "content writer",
            "marketing",
            "sales",
            "talent acquisition",
            "human resources",
            "hr",
            "operations",
            "coordination",
            "charity",
            "secretary",
            "travel host",
            "audit agent",
            "subject matter expert",
            "sme",
            "social sector",
            "accounting",
            "logistics",
        ],
        "seniority_exclude_keywords": [
            "senior",
            "sr.",
            "lead",
            "principal",
            "staff engineer",
            "architect",
            "manager",
            "head of",
            "director",
        ],
        "blocked_companies": [
            "unified mentor",
            "webs it solution",
            "dexter's tech",
            "zenithbyte",
            "lensa",
        ],
        "paid_blocklist": [
            "unpaid",
            "without stipend",
            "no stipend",
            "volunteer",
            "incentive based",
            "performance based",
            "commission only",
            "0/month",
            "0 per month",
        ],
        "internship_hint_keywords": [
            "intern",
            "internship",
            "trainee",
            "apprentice",
            "graduate program",
        ],
        "dubious_title_keywords": [
            "training",
            "course",
            "bootcamp",
            "mentor",
            "instructor",
            "coach",
            "referral",
            "commission",
        ],
        "dubious_company_keywords": [
            "staffing",
            "recruit",
            "consultancy",
            "outsourcing",
            "talent",
            "hr services",
        ],
        "us_only_hints": [
            "united states",
            "usa",
            "u.s.",
            "us only",
            "u.s. only",
            "us residents only",
            "authorized to work in the us",
            "work authorization",
            "visa sponsorship not available",
            "must be based in us",
        ],
        "global_friendly_hints": [
            "worldwide",
            "global",
            "anywhere",
            "international",
        ],

        # Internship-specific
        "strict_paid_only":                True,
        "min_stipend_inr":                 5000,
        "exclude_us_only":                 True,
        "linkedin_require_internship_hint": True,
        "linkedin_min_quality":            6,
    },

    "sources": {
        # jobspy (LinkedIn / Indeed / Glassdoor) — internships
        "cap_linkedin_indian":     10,
        "cap_linkedin_offshore":   10,
        "max_per_offshore_country": 3,
        "cap_indeed_internship":   8,
        "cap_glassdoor_internship": 8,

        # jobspy — full-time remote
        "cap_linkedin_fulltime":   8,
        "cap_indeed_fulltime":     8,
        "cap_glassdoor_fulltime":  8,

        # India-specific internship sources
        "cap_internshala":         5,
        "cap_unstop":              5,
        "cap_naukri":              8,
        "cap_unstop_hackathon":    5,

        # Community sources
        "cap_hn":                  8,

        # New sources
        "cap_yc":                  10,
        "cap_wellfound":           10,
        "cap_turing":              8,
        "cap_mercor":              8,
    },

    "locations": {
        "indian_hints": [
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
        ],
    },

    "notifications": {
        "email_recipients": [],
        "telegram_enabled": True,
        "email_enabled":    True,
    },

    "dedup": {
        "expiry_days": 60,
    },

    "autoapply": {
        "enabled":              False,
        "max_per_day":          20,
        "platforms":            ["linkedin", "indeed", "internshala"],
        "cover_letter_enabled": True,
        "use_resume_tailor":    True,
        "headless":             True,
    },

    "outreach": {
        "cold_email_enabled":       True,
        "referral_finder_enabled":  True,
        "referral_playwright":      False,
    },
}


def load_config() -> dict:
    """Load config from config.json, falling back to DEFAULT_CONFIG if missing."""
    if os.path.exists(CONFIG_FILE):
        stored = _deep_copy(DEFAULT_CONFIG)
        with open(CONFIG_FILE, "r") as f:
            on_disk = json.load(f)
        _deep_merge(stored, on_disk)
        return stored
    return _deep_copy(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def generate_default_config() -> None:
    if not os.path.exists(CONFIG_FILE):
        save_config(_deep_copy(DEFAULT_CONFIG))


def _deep_copy(obj):
    return json.loads(json.dumps(obj))


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base (in place)."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
