#!/usr/bin/env python3
"""
Internship Hunter — Web Config Panel
Run locally with: python app.py
Then open: http://localhost:5000
"""

import subprocess
import sys
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, redirect, url_for, flash
from config_manager import load_config, save_config

_PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applicant_profile.json")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "internship-hunter-local")


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list_to_lines(items: list) -> str:
    return "\n".join(str(i) for i in items)


def _setup_status() -> dict:
    config = load_config()
    return {
        "gmail_user":       bool(os.environ.get("GMAIL_USER")),
        "gmail_password":   bool(os.environ.get("GMAIL_APP_PASSWORD")),
        "telegram_token":   bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "telegram_chat":    bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "email_recipients": bool(config["notifications"]["email_recipients"]),
        "has_keywords":     bool(
            config["search"].get("jobspy_internship_keywords")
            or config["search"].get("internshala_terms")
        ),
    }


@app.route("/")
def dashboard():
    config = load_config()
    src = config["sources"]
    flt = config["filters"]
    sch = config["search"]
    stats = {
        # Search counts
        "jobspy_intern_keywords":   len(sch.get("jobspy_internship_keywords", [])),
        "jobspy_fulltime_keywords": len(sch.get("jobspy_fulltime_keywords", [])),
        "internshala_terms":        len(sch.get("internshala_terms", [])),
        "unstop_keywords":          len(sch.get("unstop_keywords", [])),
        "yc_roles":                 len(sch.get("yc_roles", [])),
        "wellfound_roles":          len(sch.get("wellfound_roles", [])),
        "mercor_keywords":          len(sch.get("mercor_keywords", [])),
        # Filter stats
        "tech_include":             len(flt["tech_include_keywords"]),
        "tech_exclude":             len(flt["tech_exclude_keywords"]),
        "blocked_companies":        len(flt["blocked_companies"]),
        "min_stipend_inr":          flt["min_stipend_inr"],
        "min_salary_usd":           flt.get("min_salary_usd_annual", 40000),
        "strict_paid_only":         flt["strict_paid_only"],
        "exclude_us_only":          flt["exclude_us_only"],
        "enable_internships":       flt.get("enable_internships", True),
        "enable_full_time_remote":  flt.get("enable_full_time_remote", True),
        "linkedin_min_quality":     flt["linkedin_min_quality"],
        # Source caps
        "cap_linkedin_indian":      src.get("cap_linkedin_indian", 10),
        "cap_linkedin_offshore":    src.get("cap_linkedin_offshore", 10),
        "cap_indeed_internship":    src.get("cap_indeed_internship", 8),
        "cap_glassdoor_internship": src.get("cap_glassdoor_internship", 8),
        "cap_linkedin_fulltime":    src.get("cap_linkedin_fulltime", 8),
        "cap_indeed_fulltime":      src.get("cap_indeed_fulltime", 8),
        "cap_glassdoor_fulltime":   src.get("cap_glassdoor_fulltime", 8),
        "cap_internshala":          src.get("cap_internshala", 5),
        "cap_unstop":               src.get("cap_unstop", 5),
        "cap_yc":                   src.get("cap_yc", 10),
        "cap_wellfound":            src.get("cap_wellfound", 10),
        "cap_turing":               src.get("cap_turing", 8),
        "cap_mercor":               src.get("cap_mercor", 8),
        # Misc
        "email_recipients":         config["notifications"]["email_recipients"],
        "expiry_days":              config["dedup"]["expiry_days"],
    }
    return render_template("dashboard.html", stats=stats, setup=_setup_status())


@app.route("/search", methods=["GET", "POST"])
def search():
    config = load_config()
    if request.method == "POST":
        s = config["search"]
        s["jobspy_internship_keywords"] = _lines_to_list(request.form.get("jobspy_internship_keywords", ""))
        s["jobspy_fulltime_keywords"]   = _lines_to_list(request.form.get("jobspy_fulltime_keywords", ""))
        s["internshala_terms"]          = _lines_to_list(request.form.get("internshala_terms", ""))
        s["unstop_keywords"]            = _lines_to_list(request.form.get("unstop_keywords", ""))
        s["yc_roles"]                   = _lines_to_list(request.form.get("yc_roles", ""))
        s["wellfound_roles"]            = _lines_to_list(request.form.get("wellfound_roles", ""))
        s["mercor_keywords"]            = _lines_to_list(request.form.get("mercor_keywords", ""))
        s["turing_urls"]                = _lines_to_list(request.form.get("turing_urls", ""))
        save_config(config)
        flash("Search keywords saved.", "success")
        return redirect(url_for("search"))
    return render_template("search.html", config=config, to_lines=_list_to_lines)


@app.route("/filters", methods=["GET", "POST"])
def filters():
    config = load_config()
    if request.method == "POST":
        f = config["filters"]
        f["tech_include_keywords"]          = _lines_to_list(request.form.get("tech_include", ""))
        f["tech_exclude_keywords"]          = _lines_to_list(request.form.get("tech_exclude", ""))
        f["seniority_exclude_keywords"]     = _lines_to_list(request.form.get("seniority_exclude", ""))
        f["enable_internships"]             = request.form.get("enable_internships") == "on"
        f["enable_full_time_remote"]        = request.form.get("enable_full_time_remote") == "on"
        f["strict_paid_only"]               = request.form.get("strict_paid_only") == "on"
        f["min_stipend_inr"]                = int(request.form.get("min_stipend_inr", 5000) or 5000)
        f["min_salary_usd_annual"]          = int(request.form.get("min_salary_usd_annual", 40000) or 40000)
        f["exclude_us_only"]                = request.form.get("exclude_us_only") == "on"
        f["full_time_require_remote_hint"]  = request.form.get("full_time_require_remote_hint") == "on"
        f["linkedin_require_internship_hint"] = request.form.get("linkedin_require_internship_hint") == "on"
        f["linkedin_min_quality"]           = int(request.form.get("linkedin_min_quality", 6) or 6)
        f["full_time_min_quality"]          = int(request.form.get("full_time_min_quality", 4) or 4)
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
        # jobspy — internships
        s["cap_linkedin_indian"]       = int(request.form.get("cap_linkedin_indian", 10) or 10)
        s["cap_linkedin_offshore"]     = int(request.form.get("cap_linkedin_offshore", 10) or 10)
        s["max_per_offshore_country"]  = int(request.form.get("max_per_offshore_country", 3) or 3)
        s["cap_indeed_internship"]     = int(request.form.get("cap_indeed_internship", 8) or 8)
        s["cap_glassdoor_internship"]  = int(request.form.get("cap_glassdoor_internship", 8) or 8)
        # jobspy — full-time
        s["cap_linkedin_fulltime"]     = int(request.form.get("cap_linkedin_fulltime", 8) or 8)
        s["cap_indeed_fulltime"]       = int(request.form.get("cap_indeed_fulltime", 8) or 8)
        s["cap_glassdoor_fulltime"]    = int(request.form.get("cap_glassdoor_fulltime", 8) or 8)
        # India-specific
        s["cap_internshala"]           = int(request.form.get("cap_internshala", 5) or 5)
        s["cap_unstop"]                = int(request.form.get("cap_unstop", 5) or 5)
        # New sources
        s["cap_naukri"]                = int(request.form.get("cap_naukri", 8) or 8)
        s["cap_hn"]                    = int(request.form.get("cap_hn", 8) or 8)
        s["cap_yc"]                    = int(request.form.get("cap_yc", 10) or 10)
        s["cap_wellfound"]             = int(request.form.get("cap_wellfound", 10) or 10)
        s["cap_turing"]                = int(request.form.get("cap_turing", 8) or 8)
        s["cap_mercor"]                = int(request.form.get("cap_mercor", 8) or 8)
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


@app.route("/applications")
def applications():
    try:
        from autoapply import tracker
        tracker.init_db()
        apps  = tracker.get_all(limit=200)
        stats = tracker.get_stats()
    except Exception as e:
        apps  = []
        stats = {"total": 0, "queued": 0, "applied": 0, "failed": 0, "skipped": 0, "applying": 0}
        flash(f"Could not load applications: {e}", "error")
    tab = request.args.get("tab", "all")
    if tab != "all":
        apps = [a for a in apps if a.get("status") == tab]
    return render_template("applications.html", apps=apps, stats=stats, active_tab=tab)


@app.route("/applications/clear", methods=["POST"])
def clear_applications():
    try:
        from autoapply import tracker
        tracker.init_db()
        tracker.clear_all()
        flash("All application records cleared.", "success")
    except Exception as e:
        flash(f"Clear failed: {e}", "error")
    return redirect(url_for("applications"))


@app.route("/autoapply-settings", methods=["GET", "POST"])
def autoapply_settings():
    config = load_config()
    aa = config.setdefault("autoapply", {})

    # Load profile JSON for editor
    profile_json = ""
    if os.path.exists(_PROFILE_PATH):
        with open(_PROFILE_PATH) as f:
            profile_json = f.read()

    if request.method == "POST":
        action = request.form.get("action", "settings")

        if action == "save_profile":
            raw = request.form.get("profile_json", "").strip()
            try:
                json.loads(raw)  # validate
                with open(_PROFILE_PATH, "w") as f:
                    f.write(raw)
                flash("Applicant profile saved.", "success")
            except json.JSONDecodeError as e:
                flash(f"Invalid JSON: {e}", "error")
            return redirect(url_for("autoapply_settings"))

        # Settings form
        aa["enabled"]              = request.form.get("enabled") == "on"
        aa["cover_letter_enabled"] = request.form.get("cover_letter_enabled") == "on"
        aa["headless"]             = request.form.get("headless") == "on"
        aa["max_per_day"]          = int(request.form.get("max_per_day", 20) or 20)
        aa["platforms"] = [
            p for p in ["linkedin", "indeed", "internshala"]
            if request.form.get(f"platform_{p}") == "on"
        ]
        save_config(config)
        flash("Auto-apply settings saved.", "success")
        return redirect(url_for("autoapply_settings"))

    creds = {
        "linkedin_email":         bool(os.environ.get("LINKEDIN_EMAIL")),
        "linkedin_password":      bool(os.environ.get("LINKEDIN_PASSWORD")),
        "indeed_email":           bool(os.environ.get("INDEED_EMAIL")),
        "indeed_password":        bool(os.environ.get("INDEED_PASSWORD")),
        "internshala_email":      bool(os.environ.get("INTERNSHALA_EMAIL")),
        "internshala_password":   bool(os.environ.get("INTERNSHALA_PASSWORD")),
        "anthropic_api_key":      bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
    return render_template(
        "autoapply_settings.html",
        config=config,
        aa=aa,
        creds=creds,
        profile_json=profile_json,
    )


@app.route("/run", methods=["POST"])
def run_pipeline():
    try:
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True,
            text=True,
            timeout=2700,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            flash("Pipeline run completed successfully.", "success")
        else:
            flash(f"Pipeline run failed (exit {result.returncode}). Check your terminal for logs.", "error")
    except subprocess.TimeoutExpired:
        flash("Pipeline run timed out after 45 minutes.", "error")
    except Exception as e:
        flash(f"Failed to start pipeline: {e}", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
