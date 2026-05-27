import os
import smtplib
import logging
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
import telegram

from config_manager import load_config

logger = logging.getLogger(__name__)


def _get_recipients() -> list[str]:
    return load_config()["notifications"]["email_recipients"]


def _split_by_type(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    internships = [j for j in jobs if j.get("job_type") != "full_time_remote"]
    fulltime    = [j for j in jobs if j.get("job_type") == "full_time_remote"]
    return internships, fulltime


# ─────────────────────────────────────────────
# HTML Email Builder
# ─────────────────────────────────────────────

def _job_rows_html(items: list[dict], show_stipend: bool) -> str:
    rows = ""
    for j in items:
        comp = j.get("stipend", "") if show_stipend else j.get("salary", "")
        comp_html = (
            f'<br><span style="color:#0f766e;font-size:12px;">{"Stipend" if show_stipend else "Salary"}: {comp}</span>'
            if comp else ""
        )
        rows += f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;">
            <a href="{j['url']}" style="color:#4f46e5;font-weight:600;text-decoration:none;">{j['title']}</a><br>
            <span style="color:#555;font-size:13px;">{j['company']}</span>{comp_html}
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;color:#666;font-size:13px;">{j['location']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;font-size:13px;">
            <a href="{j['url']}" style="background:#4f46e5;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-size:12px;">Apply</a>
          </td>
        </tr>"""
    return rows


def _source_section_html(title: str, header_color: str, items: list[dict], show_stipend: bool) -> str:
    by_source: dict[str, list] = {}
    for job in items:
        by_source.setdefault(job.get("source", "Other"), []).append(job)

    sections = f"""
    <h2 style="color:#fff;margin:0 0 4px;font-size:18px;background:{header_color};padding:14px 20px;border-radius:10px 10px 0 0;">
      {title} — {len(items)} listing(s)
    </h2>
    <div style="background:#fff;border-radius:0 0 10px 10px;padding:0 0 8px;margin-bottom:24px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
    """
    for source, jobs in by_source.items():
        rows = _job_rows_html(jobs, show_stipend)
        sections += f"""
      <div style="padding:0 12px;">
        <div style="font-size:12px;color:#888;padding:10px 0 4px;border-bottom:1px solid #f0f0f0;font-weight:600;">{source} — {len(jobs)}</div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <thead>
            <tr style="background:#f7f7fb;">
              <th style="padding:8px;text-align:left;font-size:12px;color:#888;">Role &amp; Company</th>
              <th style="padding:8px;text-align:left;font-size:12px;color:#888;">Location</th>
              <th style="padding:8px;"></th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""
    sections += "</div>"
    return sections


def _build_html(jobs: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    internships, fulltime = _split_by_type(jobs)

    body = ""
    if internships:
        body += _source_section_html("📚 Internships", "#4f46e5", internships, show_stipend=True)
    if fulltime:
        body += _source_section_html("💼 Remote Full-Time Jobs", "#0f766e", fulltime, show_stipend=False)

    n_intern  = len(internships)
    n_full    = len(fulltime)
    if n_intern and n_full:
        subtitle = f"{n_intern} internship(s) + {n_full} remote job(s)"
    elif n_intern:
        subtitle = f"{n_intern} internship(s)"
    else:
        subtitle = f"{n_full} remote job(s)"

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:700px;margin:32px auto;background:#f4f4f8;padding:0 16px 32px;">
    <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:12px;padding:28px 32px;color:#fff;margin-bottom:24px;">
      <h1 style="margin:0 0 6px;font-size:22px;">🎯 Daily Job Digest</h1>
      <p style="margin:0;opacity:0.85;font-size:14px;">{today} · {subtitle}</p>
    </div>
    {body if jobs else '<p style="text-align:center;color:#888;padding:40px 0;">No new jobs found today. Check back tomorrow!</p>'}
    <p style="text-align:center;color:#aaa;font-size:12px;margin-top:24px;">
      Powered by Internship Hunter · Running on GitHub Actions
    </p>
  </div>
</body>
</html>"""


def send_email(jobs: list[dict]) -> bool:
    smtp_user = os.environ.get("GMAIL_USER")
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD")
    recipients = _get_recipients()

    if not smtp_user or not smtp_pass:
        logger.warning("GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping email.")
        return False
    if not recipients:
        logger.warning("No email recipients configured — skipping email.")
        return False

    internships, fulltime = _split_by_type(jobs)
    n_i, n_f = len(internships), len(fulltime)
    if n_i and n_f:
        subject = f"🎯 {n_i} Internships + {n_f} Remote Jobs Today — {date.today().strftime('%b %d')}"
    elif n_i:
        subject = f"🎯 {n_i} New Internships Today — {date.today().strftime('%b %d')}"
    else:
        subject = f"💼 {n_f} Remote Jobs Today — {date.today().strftime('%b %d')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(_build_html(jobs), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipients, msg.as_string())

    logger.info(f"Email sent to {recipients} with {len(jobs)} jobs.")
    return True


# ─────────────────────────────────────────────
# Telegram Notifier — interactive job cards
# ─────────────────────────────────────────────

# Platforms the auto-apply bot can handle
_APPLY_PLATFORMS = {"LinkedIn", "Indeed", "Internshala", "Naukri"}


def _esc(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_job_card(job: dict) -> str:
    """Format a single job as an HTML card for Telegram."""
    is_intern = job.get("job_type") != "full_time_remote"
    icon  = "📚" if is_intern else "💼"
    jtype = "Internship" if is_intern else "Full-Time"
    comp  = job.get("stipend") or job.get("salary") or ""

    lines = [
        f"{icon} <b>{_esc(job.get('title', ''))}</b>",
        f"🏢 {_esc(job.get('company', ''))}",
    ]
    if job.get("location"):
        lines.append(f"📍 {_esc(job['location'])}")
    if comp:
        lines.append(f"💰 {_esc(str(comp))}")
    lines.append(f"<i>{_esc(job.get('source', ''))} · {jtype}</i>")
    return "\n".join(lines)


def _job_keyboard(job: dict):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from config_manager import load_config
    source   = job.get("source", "")
    url      = job.get("url", "")
    outreach = load_config().get("outreach", {})

    row1, row2 = [], []
    if source in _APPLY_PLATFORMS and url:
        row1.append(InlineKeyboardButton("🤖 Auto Apply", callback_data=f"apply:{source}"))
    if url:
        row1.append(InlineKeyboardButton("🔗 Open", url=url))

    if outreach.get("cold_email_enabled", True):
        row2.append(InlineKeyboardButton("📧 Cold Email", callback_data="cold_email"))
    if outreach.get("referral_finder_enabled", True):
        row2.append(InlineKeyboardButton("🤝 Referral", callback_data="find_referral"))

    rows = [r for r in [row1, row2] if r]
    return InlineKeyboardMarkup(rows) if rows else None


async def _send_telegram_async(jobs: list[dict]) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    bot  = telegram.Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    chat = os.environ["TELEGRAM_CHAT_ID"]
    today = date.today().strftime("%B %d, %Y")

    internships, fulltime = _split_by_type(jobs)

    if not jobs:
        await bot.send_message(
            chat_id=chat,
            text=f"🎯 <b>Daily Digest — {today}</b>\n\nNo new jobs found today. Check back tomorrow!",
            parse_mode="HTML",
        )
        return

    # Header summary
    await bot.send_message(
        chat_id=chat,
        text=(
            f"🎯 <b>Daily Digest — {today}</b>\n"
            f"📚 {len(internships)} internship(s)  ·  💼 {len(fulltime)} remote job(s)\n\n"
            f"Tap <b>🤖 Auto Apply</b> to apply instantly, or <b>🔗 Open</b> to apply manually."
        ),
        parse_mode="HTML",
    )

    # Individual job cards with buttons
    sent = 0
    for job in jobs:
        try:
            text = _fmt_job_card(job)
            kb   = _job_keyboard(job)
            kwargs: dict = dict(
                chat_id=chat,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            if kb:
                kwargs["reply_markup"] = kb
            await bot.send_message(**kwargs)
            sent += 1
            await asyncio.sleep(0.35)   # stay well under Telegram's 30 msg/s limit
        except Exception as e:
            logger.warning(f"Failed to send card for '{job.get('title')}': {e}")

    logger.info(f"Telegram: sent header + {sent} job card(s).")


def send_telegram(jobs: list[dict]) -> bool:
    if not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_CHAT_ID"):
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram.")
        return False
    asyncio.run(_send_telegram_async(jobs))
    return True
