#!/usr/bin/env python3
"""
Internship Hunter — Web Config Panel
Run locally with: python app.py
Then open: http://localhost:5000
"""

import subprocess
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env when running locally; no-op in CI
except ImportError:
    pass

from flask import Flask, render_template, request, redirect, url_for, flash

from config_manager import load_config, save_config

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "internship-hunter-local")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list_to_lines(items: list) -> str:
    return "\n".join(str(i) for i in items)


def _setup_status() -> dict:
    """Check which required pieces are configured. Used to render setup warnings."""
    config = load_config()
    return {
        "gmail_user":       bool(os.environ.get("GMAIL_USER")),
        "gmail_password":   bool(os.environ.get("GMAIL_APP_PASSWORD")),
        "telegram_token":   bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "telegram_chat":    bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "email_recipients": bool(config["notifications"]["email_recipients"]),
        "has_keywords":     bool(config["search"]["linkedin_keywords"]),
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    config = load_config()
    stats = {
        "linkedin_keywords":    len(config["search"]["linkedin_keywords"]),
        "linkedin_locations":   len(config["search"]["linkedin_locations"]),
        "internshala_terms":    len(config["search"]["internshala_terms"]),
        "unstop_keywords":      len(config["search"]["unstop_keywords"]),
        "tech_include":         len(config["filters"]["tech_include_keywords"]),
        "tech_exclude":         len(config["filters"]["tech_exclude_keywords"]),
        "blocked_companies":    len(config["filters"]["blocked_companies"]),
        "min_stipend_inr":      config["filters"]["min_stipend_inr"],
        "strict_paid_only":     config["filters"]["strict_paid_only"],
        "exclude_us_only":      config["filters"]["exclude_us_only"],
        "linkedin_require_hint": config["filters"]["linkedin_require_internship_hint"],
        "linkedin_min_quality": config["filters"]["linkedin_min_quality"],
        "cap_linkedin_indian":  config["sources"]["cap_linkedin_indian"],
        "cap_linkedin_offshore": config["sources"]["cap_linkedin_offshore"],
        "cap_internshala":      config["sources"]["cap_internshala"],
        "cap_unstop":           config["sources"]["cap_unstop"],
        "email_recipients":     config["notifications"]["email_recipients"],
        "expiry_days":          config["dedup"]["expiry_days"],
    }
    return render_template("dashboard.html", stats=stats, setup=_setup_status())


@app.route("/search", methods=["GET", "POST"])
def search():
    config = load_config()
    if request.method == "POST":
        config["search"]["linkedin_keywords"]  = _lines_to_list(request.form.get("linkedin_keywords", ""))
        config["search"]["linkedin_locations"] = _lines_to_list(request.form.get("linkedin_locations", ""))
        config["search"]["internshala_terms"]  = _lines_to_list(request.form.get("internshala_terms", ""))
        config["search"]["unstop_keywords"]    = _lines_to_list(request.form.get("unstop_keywords", ""))
        save_config(config)
        flash("Search keywords saved.", "success")
        return redirect(url_for("search"))
    return render_template("search.html", config=config, to_lines=_list_to_lines)


@app.route("/filters", methods=["GET", "POST"])
def filters():
    config = load_config()
    if request.method == "POST":
        f = config["filters"]
        f["tech_include_keywords"]        = _lines_to_list(request.form.get("tech_include", ""))
        f["tech_exclude_keywords"]        = _lines_to_list(request.form.get("tech_exclude", ""))
        f["seniority_exclude_keywords"]   = _lines_to_list(request.form.get("seniority_exclude", ""))
        f["strict_paid_only"]             = request.form.get("strict_paid_only") == "on"
        f["min_stipend_inr"]              = int(request.form.get("min_stipend_inr", 5000) or 5000)
        f["exclude_us_only"]              = request.form.get("exclude_us_only") == "on"
        f["linkedin_require_internship_hint"] = request.form.get("linkedin_require_internship_hint") == "on"
        f["linkedin_min_quality"]         = int(request.form.get("linkedin_min_quality", 6) or 6)
        save_config(config)
        flash("Filter settings saved.", "success")
        return redirect(url_for("filters"))
    return render_template("filters.html", config=config, to_lines=_list_to_lines)


@app.route("/blocked", methods=["GET", "POST"])
def blocked():
    config = load_config()
    if request.method == "POST":
        config["filters"]["blocked_companies"]        = _lines_to_list(request.form.get("blocked_companies", ""))
        config["filters"]["dubious_title_keywords"]   = _lines_to_list(request.form.get("dubious_title_keywords", ""))
        config["filters"]["dubious_company_keywords"] = _lines_to_list(request.form.get("dubious_company_keywords", ""))
        config["filters"]["paid_blocklist"]           = _lines_to_list(request.form.get("paid_blocklist", ""))
        save_config(config)
        flash("Block lists saved.", "success")
        return redirect(url_for("blocked"))
    return render_template("blocked.html", config=config, to_lines=_list_to_lines)


@app.route("/sources", methods=["GET", "POST"])
def sources():
    config = load_config()
    if request.method == "POST":
        s = config["sources"]
        s["linkedin_max_pages"]        = int(request.form.get("linkedin_max_pages", 1) or 1)
        s["cap_linkedin_indian"]       = int(request.form.get("cap_linkedin_indian", 10) or 10)
        s["cap_linkedin_offshore"]     = int(request.form.get("cap_linkedin_offshore", 10) or 10)
        s["max_per_offshore_country"]  = int(request.form.get("max_per_offshore_country", 3) or 3)
        s["cap_internshala"]           = int(request.form.get("cap_internshala", 5) or 5)
        s["cap_unstop"]                = int(request.form.get("cap_unstop", 5) or 5)
        config["dedup"]["expiry_days"] = int(request.form.get("expiry_days", 60) or 60)
        save_config(config)
        flash("Source settings saved.", "success")
        return redirect(url_for("sources"))
    return render_template("sources.html", config=config)


@app.route("/locations", methods=["GET", "POST"])
def locations():
    config = load_config()
    if request.method == "POST":
        config["locations"]["indian_hints"]        = _lines_to_list(request.form.get("indian_hints", ""))
        config["filters"]["us_only_hints"]         = _lines_to_list(request.form.get("us_only_hints", ""))
        config["filters"]["global_friendly_hints"] = _lines_to_list(request.form.get("global_friendly_hints", ""))
        save_config(config)
        flash("Location settings saved.", "success")
        return redirect(url_for("locations"))
    return render_template("locations.html", config=config, to_lines=_list_to_lines)


@app.route("/notifications", methods=["GET", "POST"])
def notifications():
    config = load_config()
    if request.method == "POST":
        config["notifications"]["email_recipients"] = _lines_to_list(request.form.get("email_recipients", ""))
        config["notifications"]["email_enabled"]    = request.form.get("email_enabled") == "on"
        config["notifications"]["telegram_enabled"] = request.form.get("telegram_enabled") == "on"
        save_config(config)
        flash("Notification settings saved.", "success")
        return redirect(url_for("notifications"))
    return render_template("notifications.html", config=config, to_lines=_list_to_lines)


@app.route("/run", methods=["POST"])
def run_pipeline():
    try:
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            flash("Pipeline run completed successfully.", "success")
        else:
            flash(f"Pipeline run failed (exit {result.returncode}). Check your terminal for logs.", "error")
    except subprocess.TimeoutExpired:
        flash("Pipeline run timed out after 30 minutes.", "error")
    except Exception as e:
        flash(f"Failed to start pipeline: {e}", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
