"""
Internshala apply automation.
Handles the standard "Apply Now" form with cover letter / "Why should you be hired?" field.
"""

import os
import logging

from .base_applier import BasePlatformApplier

logger = logging.getLogger(__name__)


class InternshalaApplier(BasePlatformApplier):
    PLATFORM = "Internshala"

    # ── Login ──────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        email    = os.environ.get("INTERNSHALA_EMAIL", "")
        password = os.environ.get("INTERNSHALA_PASSWORD", "")
        if not email or not password:
            logger.warning("Internshala: INTERNSHALA_EMAIL or INTERNSHALA_PASSWORD not set")
            return False

        try:
            self._page.goto("https://internshala.com/login/student", timeout=30000)
            self._human_delay(1000, 2000)

            self._type_human("input#email", email)
            self._human_delay(300, 600)
            self._type_human("input#password", password)
            self._human_delay(400, 800)

            self._page.click("button#login_submit")
            self._human_delay(2000, 3500)

            # Check logged in via URL or profile element presence
            if "login" not in self._page.url:
                return True
            # Also check for the dashboard nav element
            try:
                el = self._page.query_selector(".profile_container, .user-name, #user_name_display")
                if el:
                    return True
            except Exception:
                pass

            logger.warning(f"Internshala: login unclear — URL is {self._page.url}")
            return False

        except Exception as e:
            logger.error(f"Internshala login error: {e}")
            return False

    # ── Apply ──────────────────────────────────────────────────────────────────

    def apply(self, job: dict, cover_letter: str) -> tuple[bool, str]:
        url = str(job.get("url", ""))
        try:
            self._page.goto(url, timeout=30000)
            self._human_delay(1500, 2500)

            # Click "Apply Now"
            apply_btn = self._find_apply_button()
            if not apply_btn:
                return False, "no_apply_button"

            apply_btn.click()
            self._human_delay(1000, 2000)

            # Fill availability / joining date
            availability = self.profile.get("common_answers", {}).get("availability", "Immediately")
            for sel in [
                "input#availability",
                "input[name='availability']",
                "input[placeholder*='available']",
                "input[placeholder*='joining']",
            ]:
                self._fill_if_empty(sel, availability)

            # Fill "Why should you be hired?" / cover letter field
            why_text = cover_letter or self.profile.get("common_answers", {}).get("why_this_role", "")
            for sel in [
                "textarea#cover_letter_text",
                "textarea[name='cover_letter']",
                "textarea[placeholder*='why']",
                "textarea[placeholder*='cover']",
                "textarea",
            ]:
                try:
                    el = self._page.query_selector(sel)
                    if el and el.is_visible():
                        current = (el.input_value() or "").strip()
                        if not current and why_text:
                            el.click()
                            el.fill(why_text)
                        break
                except Exception:
                    pass

            self._human_delay(500, 1000)

            # Submit
            submitted = False
            for sel in [
                "button#submit",
                "button[type='submit']",
                "input[type='submit']",
                "button.btn-primary",
            ]:
                try:
                    btn = self._page.query_selector(sel)
                    if btn and btn.is_visible() and btn.is_enabled():
                        # Avoid clicking the main "Apply Now" button again
                        text = (btn.inner_text() or btn.get_attribute("value") or "").lower()
                        if "apply now" in text:
                            continue
                        btn.click()
                        self._human_delay(1500, 2500)
                        submitted = True
                        break
                except Exception:
                    pass

            if not submitted:
                return False, "submit_button_not_found"

            # Confirm success via page content or URL change
            page_text = (self._page.content() or "").lower()
            url_after  = self._page.url

            if any(w in page_text for w in ["application sent", "successfully applied", "thank you", "applied"]):
                return True, ""
            if "application" in url_after or "success" in url_after:
                return True, ""

            return False, "submission_unclear"

        except Exception as e:
            logger.error(f"Internshala apply error for {url}: {e}")
            return False, str(e)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _find_apply_button(self):
        selectors = [
            "a#apply_now_disabled_link",
            "a.apply_now_btn",
            "button.apply_now_btn",
            "#apply_now_btn",
            "a[id*='apply']",
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
            for el in self._page.query_selector_all("a, button"):
                text = (el.inner_text() or "").lower().strip()
                if text in ("apply now", "apply"):
                    if el.is_visible():
                        return el
        except Exception:
            pass
        return None
