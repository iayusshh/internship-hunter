"""
Cover letter generator — uses Claude Haiku via the Anthropic SDK.
Falls back to a fixed template if ANTHROPIC_API_KEY is not set.
"""

import os
import logging

logger = logging.getLogger(__name__)

_TEMPLATE = """Dear Hiring Team,

I came across the {job_title} role at {company} and am very excited about the opportunity. {company}'s work aligns closely with my interests and technical background.

As a software engineering student passionate about building reliable, scalable systems, I have hands-on experience with backend development, APIs, and modern web technologies. I am eager to contribute meaningfully from day one.

I am available immediately and would welcome the chance to discuss how I can add value to your team.

Best regards,
{full_name}"""


def generate_cover_letter(
    job_title: str,
    company: str,
    description: str,
    profile: dict,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using template cover letter")
        return _TEMPLATE.format(
            job_title=job_title,
            company=company,
            full_name=profile.get("full_name", "Applicant"),
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""Write a concise 3-paragraph cover letter for this job application.

Role: {job_title} at {company}
Job description: {(description or "Not available")[:600]}

Applicant background:
- Name: {profile.get("full_name", "")}
- Education: {profile.get("education", "")}
- Bio: {profile.get("bio", "")}
- GitHub: {profile.get("github_url", "")}
- Portfolio: {profile.get("portfolio_url", "")}

Rules:
- Under 200 words total
- No generic opener like "I am writing to express my interest"
- Paragraph 1: be specific about the company or role
- Paragraph 2: highlight one concrete technical project or skill from the bio
- Paragraph 3: close with availability ({profile.get("common_answers", {}).get("availability", "Immediate")}) and genuine enthusiasm
- Sign off with the applicant's name"""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    except Exception as e:
        logger.warning(f"Cover letter generation failed: {e} — using template")
        return _TEMPLATE.format(
            job_title=job_title,
            company=company,
            full_name=profile.get("full_name", "Applicant"),
        )
