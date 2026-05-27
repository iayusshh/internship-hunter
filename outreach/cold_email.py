"""
Cold email outreach — find a company contact email, draft a personalized
message with Claude, and send it via Gmail SMTP.
"""

import logging
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Generic recruiter/HR email patterns to try (ordered by likelihood)
_HR_PATTERNS = [
    "careers@{domain}",
    "jobs@{domain}",
    "hiring@{domain}",
    "hr@{domain}",
    "talent@{domain}",
    "recruit@{domain}",
    "internships@{domain}",
]

_HUNTER_URL = "https://api.hunter.io/v2/domain-search"


# ── Domain inference ────────────────────────────────────────────────────────────

def _domain_from_job_url(job_url: str) -> str | None:
    """Extract company domain from the job URL if it's not a job board."""
    job_boards = {
        "linkedin.com", "indeed.com", "glassdoor.com", "wellfound.com",
        "workatastartup.com", "internshala.com", "unstop.com", "naukri.com",
        "turing.com", "mercor.com", "news.ycombinator.com",
    }
    try:
        netloc = urlparse(job_url).netloc.lower().replace("www.", "")
        if netloc and not any(netloc == jb or netloc.endswith("." + jb) for jb in job_boards):
            return netloc
    except Exception:
        pass
    return None


def _domain_from_company_name(company: str) -> str:
    """Best-guess domain from a company name."""
    clean = re.sub(
        r'\b(inc|ltd|llc|pvt|limited|technologies|tech|solutions|labs|ai|'
        r'software|systems|group|global|international|co\.)\b',
        "",
        company.lower(),
        flags=re.I,
    ).strip()
    clean = re.sub(r"[^a-z0-9]", "", clean)
    return f"{clean}.com" if clean else ""


def infer_domain(company: str, job_url: str = "") -> str:
    return _domain_from_job_url(job_url) or _domain_from_company_name(company)


# ── Email finding ───────────────────────────────────────────────────────────────

def find_via_hunter(domain: str) -> list[str]:
    """Query Hunter.io for emails at a domain. Returns [] if no API key or quota exceeded."""
    api_key = os.environ.get("HUNTER_API_KEY", "")
    if not api_key or not domain:
        return []
    try:
        resp = requests.get(
            _HUNTER_URL,
            params={"domain": domain, "api_key": api_key, "type": "personal", "limit": 3},
            timeout=8,
        )
        if resp.status_code != 200:
            return []
        emails = resp.json().get("data", {}).get("emails", [])
        # Prefer HR / recruiter titles
        ranked = sorted(
            emails,
            key=lambda e: any(
                t in (e.get("type") or e.get("position") or "").lower()
                for t in ("hr", "talent", "recruit", "hiring", "people")
            ),
            reverse=True,
        )
        return [e["value"] for e in ranked[:2] if e.get("value")]
    except Exception as e:
        logger.debug(f"Hunter.io query failed: {e}")
        return []


def guess_emails(domain: str) -> list[str]:
    """Return a short list of pattern-guessed emails for HR/recruiting."""
    if not domain:
        return []
    return [p.format(domain=domain) for p in _HR_PATTERNS[:4]]


def find_email(company: str, job_url: str = "") -> tuple[str, str]:
    """
    Returns (email, method) where method is 'hunter' | 'pattern' | ''.
    Tries Hunter.io first, then pattern guessing.
    """
    domain = infer_domain(company, job_url)
    if not domain:
        return "", ""

    hunter_emails = find_via_hunter(domain)
    if hunter_emails:
        return hunter_emails[0], "hunter"

    guesses = guess_emails(domain)
    if guesses:
        return guesses[0], "pattern"

    return "", ""


# ── Email drafting ──────────────────────────────────────────────────────────────

_TEMPLATE_EMAIL = """\
Hi,

I came across the {job_title} opportunity at {company} and wanted to reach out directly.

I'm a software engineering student with experience in {skills}. I'm passionate about building real-world systems and am actively looking for an internship where I can contribute from day one.

Would love to learn more about any openings at {company} — happy to share my resume or jump on a quick call.

Thanks for your time,
{full_name}
{linkedin}"""


def draft_cold_email(
    job_title: str,
    company: str,
    profile: dict,
) -> tuple[str, str]:
    """Returns (subject, body). Uses Claude if API key is set, else a template."""
    full_name = profile.get("full_name", "Applicant")
    skills    = profile.get("bio", "backend development, Python, and APIs") or "software engineering"
    linkedin  = profile.get("linkedin_url", "")
    api_key   = os.environ.get("ANTHROPIC_API_KEY", "")

    subject = f"{job_title} — Application from {full_name}"

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = f"""Write a cold email to a recruiter/HR at {company} for a {job_title} position.

Applicant: {full_name}
Bio: {profile.get('bio', '')}
Education: {profile.get('education', '')}
GitHub: {profile.get('github_url', '')}
LinkedIn: {linkedin}

Rules:
- Under 120 words
- No "I am writing to express my interest"
- Personal and direct — mention something specific about {company} if possible
- End with the applicant's name and LinkedIn URL
- Subject line (first line): {subject}
- Then the email body"""

            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            body = msg.content[0].text.strip()
            # Strip subject line if Claude included it
            lines = body.split("\n")
            if lines and subject.lower() in lines[0].lower():
                body = "\n".join(lines[1:]).strip()
            return subject, body
        except Exception as e:
            logger.warning(f"Cold email draft failed: {e} — using template")

    body = _TEMPLATE_EMAIL.format(
        job_title=job_title,
        company=company,
        skills=skills[:80],
        full_name=full_name,
        linkedin=linkedin,
    )
    return subject, body


# ── Sending ─────────────────────────────────────────────────────────────────────

def send_cold_email(to_email: str, subject: str, body: str) -> bool:
    """Send email via Gmail SMTP. Returns True on success."""
    smtp_user = os.environ.get("GMAIL_USER", "")
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not smtp_user or not smtp_pass:
        logger.warning("Cold email: GMAIL_USER or GMAIL_APP_PASSWORD not set")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = smtp_user
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        logger.info(f"Cold email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Cold email send failed: {e}")
        return False
