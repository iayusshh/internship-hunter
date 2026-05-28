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
import time
import threading
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import queue
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
from config_manager import load_config, save_config

logger = logging.getLogger(__name__)

_PROFILE_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applicant_profile.json")

# ── Pipeline streaming state ───────────────────────────────────────────────────
_pipeline_state: dict = {"running": False, "status": "idle", "log": []}
_pipeline_listeners: list[queue.Queue] = []
_pipeline_lock_obj = threading.Lock()


def _pipeline_broadcast(line: str) -> None:
    with _pipeline_lock_obj:
        _pipeline_state["log"].append(line)
        for q in list(_pipeline_listeners):
            try:
                q.put_nowait(line)
            except queue.Full:
                pass


def _run_pipeline_thread() -> None:
    with _pipeline_lock_obj:
        _pipeline_state["running"] = True
        _pipeline_state["status"] = "running"
        _pipeline_state["log"] = []

    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env={**os.environ},
        )
        for raw_line in proc.stdout:
            _pipeline_broadcast(raw_line.rstrip("\n"))
        proc.wait()
        final = "done" if proc.returncode == 0 else "failed"
    except Exception as exc:
        _pipeline_broadcast(f"ERROR: {exc}")
        final = "failed"

    with _pipeline_lock_obj:
        _pipeline_state["running"] = False
        _pipeline_state["status"] = final
    _pipeline_broadcast(f"__done__{final}")
_JOBS_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_run_jobs.json")

# In-memory apply status: url → "applying" | "applied" | "failed:<reason>"
_apply_status: dict[str, str] = {}
_apply_lock = threading.Lock()


def _load_jobs_cache() -> tuple[list, float]:
    if not os.path.exists(_JOBS_CACHE_PATH):
        return [], 0.0
    try:
        with open(_JOBS_CACHE_PATH) as f:
            data = json.load(f)
        return data.get("jobs", []), float(data.get("fetched_at", 0))
    except Exception:
        return [], 0.0


def _run_apply_background(job: dict) -> None:
    url    = job.get("url", "")
    source = job.get("source", "")
    title  = job.get("company", "")
    company = job.get("company", "")
    jtype  = job.get("job_type", "internship")

    try:
        from autoapply.linkedin_applier    import LinkedInApplier
        from autoapply.indeed_applier      import IndeedApplier
        from autoapply.internshala_applier import InternshalaApplier
        from autoapply.naukri_applier      import NaukriApplier
        from autoapply.unstop_applier      import UnstopApplier
        from autoapply.cover_letter        import generate_cover_letter
        from autoapply.resume_tailor       import tailor_cover_letter
        from autoapply import tracker

        platform_map = {
            "LinkedIn":          LinkedInApplier,
            "Indeed":            IndeedApplier,
            "Internshala":       InternshalaApplier,
            "Naukri":            NaukriApplier,
            "Unstop":            UnstopApplier,
            "Unstop Hackathons": UnstopApplier,
        }

        ApplierClass = platform_map.get(source)
        if not ApplierClass:
            with _apply_lock:
                _apply_status[url] = f"failed:{source} not supported"
            return

        profile = None
        if os.path.exists(_PROFILE_PATH):
            with open(_PROFILE_PATH) as f:
                profile = json.load(f)
        if not profile or not profile.get("full_name"):
            with _apply_lock:
                _apply_status[url] = "failed:profile not configured"
            return

        cfg = load_config().get("autoapply", {})
        headless = bool(cfg.get("headless", True))

        cover_letter = ""
        if cfg.get("cover_letter_enabled", True) and jtype != "hackathon":
            try:
                if cfg.get("use_resume_tailor", True):
                    cover_letter = tailor_cover_letter(title, company, "", profile)
                else:
                    cover_letter = generate_cover_letter(title, company, "", profile)
            except Exception as e:
                logger.warning(f"Cover letter gen failed: {e}")

        tracker.init_db()
        app_id = tracker.add_job(job)
        tracker.update_status(app_id, "applying")

        applier = ApplierClass(profile, headless=headless)
        success, error = False, "unknown"
        try:
            applier.start()
            if not applier.login():
                error = "login_failed"
            else:
                success, error = applier.apply(job, cover_letter)
        except Exception as e:
            error = str(e)[:120]
        finally:
            applier.stop()

        tracker.update_status(
            app_id,
            "applied" if success else "failed",
            error_msg=None if success else error,
            cover_letter=cover_letter or None,
        )

        with _apply_lock:
            _apply_status[url] = "applied" if success else f"failed:{error[:40]}"

    except Exception as e:
        with _apply_lock:
            _apply_status[url] = f"failed:{str(e)[:40]}"
        logger.error(f"Apply background error for {url}: {e}")

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


@app.route("/jobs")
def jobs_page():
    from autoapply import tracker as _tracker
    jobs, fetched_at = _load_jobs_cache()
    _tracker.init_db()

    for job in jobs:
        url = job.get("url", "")
        if _tracker.already_applied(url):
            job["_status"] = "applied"
        else:
            with _apply_lock:
                job["_status"] = _apply_status.get(url, "pending")

    internships = [j for j in jobs if j.get("job_type") == "internship"]
    fulltime    = [j for j in jobs if j.get("job_type") == "full_time_remote"]
    hackathons  = [j for j in jobs if j.get("job_type") == "hackathon"]
    fetched_str = time.strftime("%d %b %Y, %I:%M %p", time.localtime(fetched_at)) if fetched_at else None
    tab = request.args.get("tab", "internships")
    return render_template(
        "jobs.html",
        internships=internships,
        fulltime=fulltime,
        hackathons=hackathons,
        fetched_at=fetched_str,
        active_tab=tab,
    )


@app.route("/jobs/apply", methods=["POST"])
def jobs_apply():
    from autoapply import tracker as _tracker
    data    = request.get_json(force=True) or {}
    url     = data.get("url", "")
    source  = data.get("source", "")
    if not url or not source:
        return jsonify({"error": "missing url or source"}), 400

    _tracker.init_db()
    if _tracker.already_applied(url):
        return jsonify({"status": "applied"})

    with _apply_lock:
        if _apply_status.get(url) == "applying":
            return jsonify({"status": "applying"})
        _apply_status[url] = "applying"

    job = {
        "url":      url,
        "source":   source,
        "title":    data.get("title", ""),
        "company":  data.get("company", ""),
        "job_type": data.get("job_type", "internship"),
    }
    t = threading.Thread(target=_run_apply_background, args=(job,), daemon=True)
    t.start()
    return jsonify({"status": "applying"})


@app.route("/jobs/apply_status")
def jobs_apply_status():
    from autoapply import tracker as _tracker
    url = request.args.get("url", "")
    _tracker.init_db()
    if _tracker.already_applied(url):
        return jsonify({"status": "applied"})
    with _apply_lock:
        status = _apply_status.get(url, "pending")
    return jsonify({"status": status})


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
        s["cap_unstop_hackathon"]      = int(request.form.get("cap_unstop_hackathon", 10) or 10)
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


_HACKATHON_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".hackathons_cache.json")


def _load_hackathon_cache() -> tuple[list, float]:
    if not os.path.exists(_HACKATHON_CACHE):
        return [], 0.0
    try:
        with open(_HACKATHON_CACHE) as f:
            data = json.load(f)
        return data.get("hackathons", []), float(data.get("fetched_at", 0))
    except Exception:
        return [], 0.0


def _save_hackathon_cache(hackathons: list) -> None:
    with open(_HACKATHON_CACHE, "w") as f:
        json.dump({"fetched_at": time.time(), "hackathons": hackathons}, f)


@app.route("/hackathons")
def hackathons_page():
    hackathons, fetched_at = _load_hackathon_cache()
    fetched_str = time.strftime("%d %b %Y, %I:%M %p", time.localtime(fetched_at)) if fetched_at else None
    return render_template("hackathons.html", hackathons=hackathons, fetched_at=fetched_str)


@app.route("/hackathons/refresh", methods=["POST"])
def hackathons_refresh():
    try:
        from scrapers.unstop_scraper import scrape_unstop_hackathons
        from job_filters import hackathon_quality_score
        raw = scrape_unstop_hackathons()
        ranked = sorted(raw, key=hackathon_quality_score, reverse=True)[:10]
        _save_hackathon_cache(ranked)
        flash(f"Fetched {len(ranked)} hackathons from Unstop.", "success")
    except Exception as e:
        flash(f"Scrape failed: {e}", "error")
    return redirect(url_for("hackathons_page"))


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
            p for p in ["linkedin", "indeed", "internshala", "naukri", "unstop"]
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
        "naukri_email":           bool(os.environ.get("NAUKRI_EMAIL")),
        "naukri_password":        bool(os.environ.get("NAUKRI_PASSWORD")),
        "unstop_email":           bool(os.environ.get("UNSTOP_EMAIL")),
        "unstop_password":        bool(os.environ.get("UNSTOP_PASSWORD")),
        "anthropic_api_key":      bool(os.environ.get("ANTHROPIC_API_KEY")),
        "hunter_api_key":         bool(os.environ.get("HUNTER_API_KEY")),
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
    with _pipeline_lock_obj:
        already = _pipeline_state["running"]
        if not already:
            t = threading.Thread(target=_run_pipeline_thread, daemon=True)
            t.start()
    return jsonify({"started": not already, "running": True})


@app.route("/run/stream")
def run_stream():
    def generate():
        with _pipeline_lock_obj:
            history = list(_pipeline_state["log"])
            running = _pipeline_state["running"]
            status  = _pipeline_state["status"]

        for line in history:
            yield f"data: {json.dumps(line)}\n\n"

        if not running:
            yield f"data: {json.dumps('__done__' + status)}\n\n"
            return

        q: queue.Queue = queue.Queue(maxsize=1000)
        with _pipeline_lock_obj:
            _pipeline_listeners.append(q)
        try:
            while True:
                try:
                    line = q.get(timeout=30)
                    yield f"data: {json.dumps(line)}\n\n"
                    if line.startswith("__done__"):
                        break
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _pipeline_lock_obj:
                if q in _pipeline_listeners:
                    _pipeline_listeners.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/run/status")
def run_status():
    with _pipeline_lock_obj:
        return jsonify({
            "running": _pipeline_state["running"],
            "status":  _pipeline_state["status"],
            "lines":   len(_pipeline_state["log"]),
        })


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True, use_reloader=False)
