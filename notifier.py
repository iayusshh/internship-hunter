import os
import smtplib
import logging
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
import telegram

logger = logging.getLogger(__name__)

RECIPIENT_EMAIL = "YOUR_EMAIL@example.com"


# ─────────────────────────────────────────────
# HTML Email Builder
# ─────────────────────────────────────────────

def _build_html(jobs: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")

    by_source: dict[str, list] = {}
    for job in jobs:
        src = job.get("source", "Other")
        by_source.setdefault(src, []).append(job)

    sections = ""
    for source, items in by_source.items():
        rows = ""
        for j in items:
            rows += f"""
            <tr>
              <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;">
                <a href="{j['url']}" style="color:#4f46e5;font-weight:600;text-decoration:none;">{j['title']}</a><br>
                <span style="color:#555;font-size:13px;">{j['company']}</span>
              </td>
              <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;color:#666;font-size:13px;">{j['location']}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #f0f0f0;font-size:13px;">
                <a href="{j['url']}" style="background:#4f46e5;color:#fff;padding:5px 12px;border-radius:4px;text-decoration:none;font-size:12px;">Apply</a>
              </td>
            </tr>"""

        sections += f"""
        <h3 style="color:#1a1a2e;margin:24px 0 8px;border-left:4px solid #4f46e5;padding-left:10px;">{source} — {len(items)} listing(s)</h3>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
          <thead>
            <tr style="background:#f7f7fb;">
              <th style="padding:10px 8px;text-align:left;font-size:13px;color:#888;">Role & Company</th>
              <th style="padding:10px 8px;text-align:left;font-size:13px;color:#888;">Location</th>
              <th style="padding:10px 8px;text-align:left;font-size:13px;color:#888;"></th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:680px;margin:32px auto;background:#f4f4f8;padding:0 16px 32px;">
    <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:12px;padding:28px 32px;color:#fff;margin-bottom:24px;">
      <h1 style="margin:0 0 6px;font-size:22px;">🎯 Daily Internship Digest</h1>
      <p style="margin:0;opacity:0.85;font-size:14px;">{today} · {len(jobs)} new listing(s) found</p>
    </div>
    {sections if jobs else '<p style="text-align:center;color:#888;padding:40px 0;">No new internships found today. Check back tomorrow!</p>'}
    <p style="text-align:center;color:#aaa;font-size:12px;margin-top:24px;">
      Powered by Internship Hunter · Running on GitHub Actions
    </p>
  </div>
</body>
</html>"""


def send_email(jobs: list[dict]):
    smtp_user = os.environ["GMAIL_USER"]
    smtp_pass = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 {len(jobs)} New Internships Today — {date.today().strftime('%b %d')}"
    msg["From"] = smtp_user
    msg["To"] = RECIPIENT_EMAIL

    html_body = _build_html(jobs)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, RECIPIENT_EMAIL, msg.as_string())

    logger.info(f"Email sent to {RECIPIENT_EMAIL} with {len(jobs)} jobs.")


# ─────────────────────────────────────────────
# Telegram Notifier
# ─────────────────────────────────────────────

def _build_telegram_message(jobs: list[dict]) -> list[str]:
    """Split into chunks ≤4096 chars (Telegram limit)."""
    today = date.today().strftime("%B %d, %Y")
    header = f"🎯 *Daily Internship Digest — {today}*\n_{len(jobs)} new listing(s) found_\n\n"

    chunks = []
    current = header

    for i, j in enumerate(jobs, 1):
        entry = (
            f"*{i}. {j['title']}*\n"
            f"🏢 {j['company']}\n"
            f"📍 {j['location']}\n"
            f"🔗 [Apply Here]({j['url']})\n"
            f"_Source: {j['source']}_\n\n"
        )
        if len(current) + len(entry) > 4000:
            chunks.append(current)
            current = entry
        else:
            current += entry

    if current.strip():
        chunks.append(current)

    if not jobs:
        chunks = [f"🎯 *Daily Internship Digest — {today}*\n\nNo new internships found today. Check back tomorrow!"]

    return chunks


async def _send_telegram_async(jobs: list[dict]):
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    bot = telegram.Bot(token=bot_token)

    chunks = _build_telegram_message(jobs)
    for chunk in chunks:
        await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    logger.info(f"Telegram message(s) sent: {len(chunks)} chunk(s).")


def send_telegram(jobs: list[dict]):
    asyncio.run(_send_telegram_async(jobs))
