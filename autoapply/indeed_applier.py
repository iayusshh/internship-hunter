"""
Indeed Quick Apply automation.
Handles 1-2 page forms for jobs with the "Easily apply" badge.
"""

import os
import logging

from .base_applier import BasePlatformApplier

logger = logging.getLogger(__name__)


class IndeedApplier(BasePlatformApplier):
    PLATFORM = "Indeed"

    # ── Login ──────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        email    = os.environ.get("INDEED_EMAIL", "")
        password = os.environ.get("INDEED_PASSWORD", "")
        if not email or not password:
            logger.warning("Indeed: INDEED_EMAIL or INDEED_PASSWORD not set")
            return False

        try:
            self._page.goto("https://secure.indeed.com/account/login", timeout=30000)
            self._human_delay(1000, 2000)

            # Fill email
            for sel in ["input#ifl-InputFormField-3", "input[name='__email']", "input[type='email']"]:
                try:
                    el = self._page.query_selector(sel)
                    if el and el.is_visible():
                        self._type_human(sel, email)
                        self._human_delay(300, 600)
                        break
                except Exception:
                    pass

            # Click continue / next
            for sel in ["button#login-submit-component", "button[type='submit']"]:
                try:
                    btn = self._page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        self._human_delay(1000, 2000)
                        break
                except Exception:
                    pass

            # Fill password (might be on next page)
            for sel in ["input#ifl-InputFormField-7", "input[name='password']", "input[type='password']"]:
                try:
                    el = self._page.query_selector(sel)
                    if el and el.is_visible():
                        self._type_human(sel, password)
                        self._human_delay(300, 600)
                        break
                except Exception:
                    pass

            # Submit
            for sel in ["button#login-submit-component", "button[type='submit']"]:
                try:
                    btn = self._page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        self._human_delay(2000, 3000)
                        break
                except Exception:
                    pass

            # Check for email verification challenge
            if "challenge" in self._page.url or "verify" in self._page.url.lower():
                logger.warning("Indeed: email verification required — skipping")
                return False

            # Success check: redirected away from login
            if "login" not in self._page.url and "indeed.com" in self._page.url:
                return True

            logger.warning(f"Indeed: login unclear — URL is {self._page.url}")
            return False

        except Exception as e:
            logger.error(f"Indeed login error: {e}")
            return False

    # ── Apply ──────────────────────────────────────────────────────────────────

    def apply(self, job: dict, cover_letter: str) -> tuple[bool, str]:
        url = str(job.get("url", ""))
        try:
            self._page.goto(url, timeout=30000)
            self._human_delay(1500, 2500)

            # Look for Easily Apply / Apply Now button
            apply_btn = self._find_apply_button()
            if not apply_btn:
                return False, "no_apply_button"

            apply_btn.click()
            self._human_delay(1000, 2000)

            # Check if redirected to an external site
            if "indeed.com" not in self._page.url:
                return False, "external_apply"

            # Fill form fields
            self._fill_form(cover_letter)
            self._human_delay(500, 1000)

            # Try to submit
            if self._try_continue_or_submit():
                self._human_delay(1500, 2500)
                # Second step if form is paginated
                if "indeed.com" in self._page.url:
                    self._fill_form(cover_letter)
                    self._human_delay(500, 1000)
                    self._try_continue_or_submit()
                    self._human_delay(1500, 2500)

            # Check for success confirmation
            page_text = (self._page.content() or "").lower()
            if any(w in page_text for w in ["application submitted", "your application", "applied"]):
                return True, ""

            return False, "submission_unclear"

        except Exception as e:
            logger.error(f"Indeed apply error for {url}: {e}")
            return False, str(e)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _find_apply_button(self):
        selectors = [
            "button[id*='indeedApplyButton']",
            "button.ia-continueButton",
            "a[id*='applyButton']",
            "span.iaLabel",
        ]
        for sel in selectors:
            try:
                el = self._page.query_selector(sel)
                if el and el.is_visible():
                    return el
            except Exception:
                pass
        # Text search
        try:
            for btn in self._page.query_selector_all("button, a"):
                text = (btn.inner_text() or "").lower().strip()
                if text in ("apply now", "easily apply", "apply"):
                    if btn.is_visible():
                        return btn
        except Exception:
            pass
        return None

    def _fill_form(self, cover_letter: str) -> None:
        profile = self.profile
        field_map = {
            "name":  profile.get("full_name", ""),
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
        }

        # Generic text inputs by placeholder or label
        for key, value in field_map.items():
            if not value:
                continue
            sel = self._find_element_by_label(key)
            if sel:
                self._fill_if_empty(sel, value)

        # Cover letter / additional info textarea
        try:
            textareas = self._page.query_selector_all("textarea")
            for ta in textareas:
                if ta.is_visible():
                    current = (ta.input_value() or "").strip()
                    if not current and cover_letter:
                        ta.click()
                        ta.fill(cover_letter)
                    break
        except Exception:
            pass

        # Resume upload if prompted
        resume_path = profile.get("resume_path", "")
        if resume_path and os.path.exists(resume_path):
            try:
                upload = self._page.query_selector("input[type='file']")
                if upload and upload.is_visible():
                    upload.set_input_files(resume_path)
                    self._human_delay(1000, 2000)
            except Exception:
                pass

    def _try_continue_or_submit(self) -> bool:
        selectors = [
            "button.ia-continueButton",
            "button[type='submit']",
            "button#form-action-continue",
            "button#form-action-submit",
        ]
        for sel in selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    btn.click()
                    self._human_delay(600, 1200)
                    return True
            except Exception:
                pass
        return False
