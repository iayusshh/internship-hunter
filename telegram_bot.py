#!/usr/bin/env python3
"""
Internship Hunter — Telegram Bot
Handles interactive job card buttons sent by the daily pipeline.

Run:
    source .venv/bin/activate
    python telegram_bot.py
"""

import json
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from autoapply import tracker
from autoapply.cover_letter        import generate_cover_letter
from autoapply.resume_tailor       import tailor_cover_letter
from autoapply.linkedin_applier    import LinkedInApplier
from autoapply.indeed_applier      import IndeedApplier
from autoapply.internshala_applier import InternshalaApplier
from autoapply.naukri_applier      import NaukriApplier
from outreach.cold_email    import find_email, draft_cold_email, send_cold_email, infer_domain
from outreach.referral_finder import find_referrals, linkedin_search_url
from config_manager import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("telegram_bot")

_PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applicant_profile.json")

_PLATFORM_MAP = {
    "LinkedIn":    LinkedInApplier,
    "Indeed":      IndeedApplier,
    "Internshala": InternshalaApplier,
    "Naukri":      NaukriApplier,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_profile() -> dict | None:
    if not os.path.exists(_PROFILE_PATH):
        return None
    with open(_PROFILE_PATH) as f:
        return json.load(f)


def _extract_url(markup) -> str | None:
    """Get the URL from the URL-type button in the inline keyboard."""
    if not markup:
        return None
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.url:
                return btn.url
    return None


def _parse_job_card(text: str) -> tuple[str, str]:
    """Extract (title, company) from a job card message."""
    title, company = "", ""
    for line in (text or "").split("\n"):
        line = line.strip()
        if not title and any(line.startswith(icon) for icon in ("📚", "💼")):
            title = line.split(" ", 1)[-1].strip()
        elif not company and line.startswith("🏢"):
            company = line.replace("🏢", "").strip()
    return title, company


async def _update_buttons(query, job_url: str, label: str, allow_retry: bool = False) -> None:
    row = [InlineKeyboardButton(label, callback_data="done")]
    if job_url:
        row.append(InlineKeyboardButton("🔗 Open", url=job_url))
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([row]))
    except Exception:
        pass


# ── Handlers ───────────────────────────────────────────────────────────────────

async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    source = (query.data or "").split(":", 1)[-1]   # "apply:LinkedIn" → "LinkedIn"
    job_url = _extract_url(query.message.reply_markup)

    if not job_url:
        await query.answer("Couldn't find the job URL.", show_alert=True)
        return

    await query.answer("Starting application…")

    # Show "Applying…" immediately
    await _update_buttons(query, job_url, "⏳ Applying…")

    # Check for duplicate
    tracker.init_db()
    if tracker.already_applied(job_url):
        await query.answer("Already applied to this job!", show_alert=True)
        await _update_buttons(query, job_url, "✅ Already applied")
        return

    # Validate platform
    ApplierClass = _PLATFORM_MAP.get(source)
    if not ApplierClass:
        await _update_buttons(query, job_url, f"❌ {source} not supported")
        return

    # Load applicant profile
    profile = _load_profile()
    if not profile or not profile.get("full_name"):
        await query.message.reply_text(
            "⚠️ <b>Applicant profile not configured.</b>\n"
            "Fill in <code>applicant_profile.json</code> and restart the bot.",
            parse_mode="HTML",
        )
        await _update_buttons(query, job_url, "❌ Profile not set")
        return

    cfg = load_config().get("autoapply", {})
    headless = bool(cfg.get("headless", True))

    # Parse job metadata from the card text
    title, company = _parse_job_card(query.message.text or "")
    jtype = "internship" if "📚" in (query.message.text or "") else "full_time_remote"
    job = {"url": job_url, "title": title, "company": company, "source": source, "job_type": jtype}

    # Generate tailored cover letter
    cover_letter = ""
    if cfg.get("cover_letter_enabled", True):
        try:
            if cfg.get("use_resume_tailor", True):
                cover_letter = tailor_cover_letter(title, company, "", profile)
            else:
                cover_letter = generate_cover_letter(title, company, "", profile)
        except Exception as e:
            logger.warning(f"Cover letter gen failed: {e}")

    # Track application
    app_id = tracker.add_job(job)
    tracker.update_status(app_id, "applying")

    # Run the applier
    applier = ApplierClass(profile, headless=headless)
    success, error = False, "unknown"
    try:
        applier.start()
        if not applier.login():
            error = "login_failed"
            await query.message.reply_text(
                f"⚠️ <b>Login failed for {source}.</b>\n"
                f"Check <code>{source.upper()}_EMAIL</code> / <code>{source.upper()}_PASSWORD</code> in your .env",
                parse_mode="HTML",
            )
        else:
            success, error = applier.apply(job, cover_letter)
    except Exception as e:
        error = str(e)[:120]
        logger.error(f"Apply exception for {job_url}: {e}")
    finally:
        applier.stop()

    # Update tracker
    tracker.update_status(
        app_id,
        "applied" if success else "failed",
        error_msg=None if success else error,
        cover_letter=cover_letter or None,
    )

    # Update buttons and send reply
    if success:
        await _update_buttons(query, job_url, "✅ Applied")
        await query.message.reply_text(
            f"✅ <b>Applied!</b>  {title} @ {company}\n<i>via {source}</i>",
            parse_mode="HTML",
        )
    else:
        short_err = (error or "unknown")[:30]
        await _update_buttons(query, job_url, f"❌ {short_err}")
        await query.message.reply_text(
            f"❌ <b>Failed:</b> {title} @ {company}\n<code>{error}</code>",
            parse_mode="HTML",
        )


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently ack taps on result badges (✅ Applied, ❌ etc)."""
    await update.callback_query.answer()


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tracker.init_db()
    stats = tracker.get_stats()
    await update.message.reply_text(
        "🤖 <b>Internship Hunter Bot</b> is running!\n\n"
        "Each morning you'll receive job cards with buttons:\n"
        "  • <b>🤖 Auto Apply</b> — applies instantly\n"
        "  • <b>🔗 Open</b> — opens job URL for manual apply\n\n"
        f"<b>All-time stats:</b> {stats['applied']} applied · {stats['failed']} failed · {stats['skipped']} skipped",
        parse_mode="HTML",
    )


async def handle_cold_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer("Finding contact email…")

    title, company = _parse_job_card(query.message.text or "")
    job_url = _extract_url(query.message.reply_markup)

    if not company:
        await query.message.reply_text("⚠️ Could not parse company name from this card.")
        return

    # Check if already emailed
    tracker.init_db()
    if tracker.already_emailed(company):
        await query.message.reply_text(
            f"ℹ️ You've already sent a cold email to <b>{company}</b>.",
            parse_mode="HTML",
        )
        return

    profile = _load_profile()
    if not profile or not profile.get("full_name"):
        await query.message.reply_text(
            "⚠️ Applicant profile not configured — fill in <code>applicant_profile.json</code>.",
            parse_mode="HTML",
        )
        return

    # Find email
    email_addr, method = find_email(company, job_url or "")
    if not email_addr:
        domain = infer_domain(company, job_url or "")
        await query.message.reply_text(
            f"❌ Couldn't find an email for <b>{company}</b>.\n"
            f"<i>Tried domain: {domain or '(unknown)'}</i>\n\n"
            "Set <code>HUNTER_API_KEY</code> in .env for better results.",
            parse_mode="HTML",
        )
        return

    # Draft email
    subject, body = draft_cold_email(title or "Internship", company, profile)

    # Save draft to DB
    outreach_id = tracker.add_outreach(company, title, email_addr, subject, body)

    # Send preview with confirm buttons
    preview = (
        f"📧 <b>Cold email draft</b>\n"
        f"<b>To:</b> <code>{email_addr}</code>  <i>({method})</i>\n"
        f"<b>Subject:</b> {subject}\n\n"
        f"{body[:600]}{'…' if len(body) > 600 else ''}"
    )
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    await query.message.reply_text(
        preview,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Send", callback_data=f"send_outreach:{outreach_id}"),
            InlineKeyboardButton("❌ Skip", callback_data=f"skip_outreach:{outreach_id}"),
        ]]),
    )


async def handle_send_outreach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    action, _, oid_str = data.partition(":")
    try:
        outreach_id = int(oid_str)
    except ValueError:
        await query.answer()
        return

    tracker.init_db()
    record = tracker.get_outreach(outreach_id)
    if not record:
        await query.answer("Record not found.", show_alert=True)
        return

    if action == "skip_outreach":
        tracker.update_outreach_status(outreach_id, "skipped")
        await query.answer("Skipped.")
        try:
            from telegram import InlineKeyboardMarkup
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[]]))
        except Exception:
            pass
        return

    # Send email
    await query.answer("Sending…")
    success = send_cold_email(record["to_email"], record["subject"], record["body"])
    if success:
        tracker.update_outreach_status(outreach_id, "sent")
        await query.edit_message_text(
            f"✅ <b>Email sent!</b>\nTo: <code>{record['to_email']}</code>\n"
            f"Subject: {record['subject']}",
            parse_mode="HTML",
        )
    else:
        tracker.update_outreach_status(outreach_id, "failed")
        await query.edit_message_text(
            "❌ <b>Send failed.</b> Check GMAIL_USER / GMAIL_APP_PASSWORD in .env.",
            parse_mode="HTML",
        )


async def handle_find_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer("Looking for referrals…")

    _, company = _parse_job_card(query.message.text or "")
    if not company:
        await query.message.reply_text("⚠️ Could not parse company name.")
        return

    cfg = load_config().get("outreach", {})
    search_url = linkedin_search_url(company)

    # Try Playwright scraping if configured
    referrals: list[dict] = []
    if cfg.get("referral_playwright", False):
        import os
        referrals = find_referrals(
            company,
            use_playwright=True,
            headless=True,
        )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    if referrals:
        lines = [f"🤝 <b>Referrals at {company}</b>\n"]
        for r in referrals[:5]:
            name  = r.get("name", "Unknown")
            title = r.get("title", "")
            purl  = r.get("profile_url", "")
            lines.append(f"• <b>{name}</b> — {title}")
        text = "\n".join(lines)
        buttons = [[InlineKeyboardButton("🔍 LinkedIn Search", url=search_url)]]
    else:
        text = (
            f"🤝 <b>Find referrals at {company}</b>\n\n"
            "Open the search below to find 2nd-degree connections.\n"
            "Message someone with a note like:\n"
            "<i>\"Hi [Name], I'm applying for a [role] at {company}. "
            "Would you be open to a quick referral or any advice?\"</i>"
        ).format(company=company)
        buttons = [[InlineKeyboardButton(f"🔍 Search at {company[:20]}", url=search_url)]]

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tracker.init_db()
    stats = tracker.get_stats()
    await update.message.reply_text(
        f"📊 <b>Application Stats</b>\n\n"
        f"✅ Applied:  {stats['applied']}\n"
        f"❌ Failed:   {stats['failed']}\n"
        f"⏭ Skipped:  {stats['skipped']}\n"
        f"⏳ Queued:   {stats['queued']}\n"
        f"📋 Total:    {stats['total']}",
        parse_mode="HTML",
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set — cannot start bot")
        sys.exit(1)

    tracker.init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",  handle_start))
    app.add_handler(CommandHandler("stats",  handle_stats))
    app.add_handler(CallbackQueryHandler(handle_apply,         pattern=r"^apply:"))
    app.add_handler(CallbackQueryHandler(handle_cold_email,    pattern=r"^cold_email$"))
    app.add_handler(CallbackQueryHandler(handle_find_referral, pattern=r"^find_referral$"))
    app.add_handler(CallbackQueryHandler(handle_send_outreach, pattern=r"^(send_outreach|skip_outreach):"))
    app.add_handler(CallbackQueryHandler(handle_noop,          pattern=r"^(noop|done)$"))

    logger.info("Bot started — polling for updates. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
