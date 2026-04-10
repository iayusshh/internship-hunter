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
        "linkedin_keywords": [
            "software engineer intern",
            "software developer intern",
            "sde intern",
            "full stack developer intern",
            "frontend developer intern",
            "backend developer intern",
            "devops intern",
            "machine learning intern",
            "ai engineer intern",
            "data engineer intern",
            "data science intern",
            "quality assurance intern",
            "software testing intern",
            "test engineer intern",
            "qa engineer intern",
            "site reliability intern",
            "sre intern",
            "platform engineer intern",
            "artificial intelligence intern",
            "ml intern",
            "android intern",
            "ios intern",
            "web developer intern",
            "app developer intern",
            "mobile developer intern",
        ],
        "linkedin_locations": [
            "India",
            "Remote",
            "United States",
            "Europe",
            "Asia",
            "England",
            "Germany",
            "Netherlands",
            "France",
            "Canada",
            "Australia",
            "New Zealand",
            "Singapore",
            "UAE",
            "Middle East",
            "Iran",
            "Indonesia",
            "Philippines",
            "Vietnam",
            "China",
            "Japan",
            "South Korea",
        ],
        "internshala_terms": [
            "software-engineer",
            "full-stack-developer",
            "web-developer",
            "frontend-developer",
            "backend-developer",
            "artificial-intelligence",
            "machine-learning",
        ],
        "unstop_keywords": [
            "software engineer",
            "full stack",
            "developer",
            "frontend",
            "backend",
            "artificial intelligence",
            "machine learning",
        ],
    },
    "filters": {
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
        "strict_paid_only": True,
        "min_stipend_inr": 5000,
        "exclude_us_only": True,
        "linkedin_require_internship_hint": True,
        "linkedin_min_quality": 6,
    },
    "sources": {
        "linkedin_max_pages": 1,
        "cap_linkedin_indian": 10,
        "cap_linkedin_offshore": 10,
        "max_per_offshore_country": 3,
        "cap_internshala": 5,
        "cap_unstop": 5,
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
        "email_recipients": [],   # add your email(s) via the web UI or directly here
        "telegram_enabled": True,
        "email_enabled": True,
    },
    "dedup": {
        "expiry_days": 60,
    },
}


def load_config() -> dict:
    """Load config from config.json, falling back to DEFAULT_CONFIG if missing."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return _deep_copy(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """Save config to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def generate_default_config() -> None:
    """Write config.json with default values if it doesn't already exist."""
    if not os.path.exists(CONFIG_FILE):
        save_config(_deep_copy(DEFAULT_CONFIG))


def _deep_copy(obj):
    """Simple deep copy via JSON round-trip."""
    return json.loads(json.dumps(obj))
