"""
Resume tailoring — rewrites cover letter with full resume context,
and generates per-job bullet points aligned to the job description.
"""

import logging
import os

logger = logging.getLogger(__name__)


def tailor_cover_letter(
    job_title: str,
    company: str,
    description: str,
    profile: dict,
) -> str:
    """
    Generate a cover letter + tailored resume bullets using the applicant's
    full resume text. Falls back gracefully if API key is absent.
    """
    resume_text = profile.get("resume_text", "").strip()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        # Defer to the basic template generator
        from .cover_letter import generate_cover_letter
        return generate_cover_letter(job_title, company, description, profile)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        resume_section = (
            f"\nApplicant's resume:\n{resume_text[:1200]}"
            if resume_text else
            f"\nApplicant bio: {profile.get('bio', '')}"
        )

        prompt = f"""You are writing a job application for a software engineering role.

Role: {job_title} at {company}
Job description excerpt: {(description or 'Not available')[:500]}
{resume_section}

Additional context:
- Name: {profile.get('full_name', '')}
- Education: {profile.get('education', '')}
- GitHub: {profile.get('github_url', '')}
- Availability: {profile.get('common_answers', {}).get('availability', 'Immediate')}

Write a cover letter in exactly 3 short paragraphs (under 200 words total):
1. Why this specific company/role is exciting (reference something concrete from the description)
2. One specific project or skill from the resume that directly maps to this role's needs
3. Availability and a confident close

No generic openers. No "I am writing to express my interest." Be direct and specific."""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=450,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    except Exception as e:
        logger.warning(f"Resume tailor API call failed: {e} — using basic cover letter")
        from .cover_letter import generate_cover_letter
        return generate_cover_letter(job_title, company, description, profile)


def tailor_resume_bullets(
    job_title: str,
    company: str,
    description: str,
    profile: dict,
) -> str:
    """
    Return 3–5 tailored resume bullet points that best match the job description.
    These can be shown in the Telegram card or pasted into application forms.
    Returns empty string if resume_text is not configured.
    """
    resume_text = profile.get("resume_text", "").strip()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not resume_text or not api_key:
        return ""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Given this job description and resume, rewrite 3–5 resume bullet points
to be most relevant for this specific role. Keep them concise, action-verb first, quantified where possible.

Job: {job_title} at {company}
Description: {(description or '')[:400]}
Resume: {resume_text[:1000]}

Output ONLY the bullet points, one per line, starting with •"""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    except Exception as e:
        logger.warning(f"tailor_resume_bullets failed: {e}")
        return ""
