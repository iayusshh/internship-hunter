"""
Naukri.com apply automation.
Requires system Chrome (channel='chrome') to bypass Akamai bot protection.
Handles the standard "Apply" button flow with optional cover letter field.
"""

import os
import logging

from .base_applier import BasePlatformApplier

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://www.naukri.com/nlogin/login"


class NaukriApplier(BasePlatformApplier):
    PLATFORM = "Naukri"

    # ── Override start() to use system Chrome ──────────────────────────────────

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                channel="chrome",
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
        except Exception:
            logger.warning("Naukri: system Chrome not found, falling back to Chromium (may be blocked)")
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        self._page = ctx.new_page()
        self._page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});"
        )

    # ── Login ──────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        email    = os.environ.get("NAUKRI_EMAIL", "")
        password = os.environ.get("NAUKRI_PASSWORD", "")
        if not email or not password:
            logger.warning("Naukri: NAUKRI_EMAIL or NAUKRI_PASSWORD not set")
            return False

        try:
            self._page.goto(_LOGIN_URL, timeout=30000)
            self._human_delay(1500, 2500)

            self._type_human("input#usernameField", email)
            self._human_delay(300, 600)
            self._type_human("input#passwordField", password)
            self._human_delay(400, 800)

            # Click the "Login" submit button (not the OTP button)
            login_btn = None
            for btn in self._page.query_selector_all("button[type='submit']"):
                text = (btn.inner_text() or "").strip().lower()
                if text == "login":
                    login_btn = btn
                    break
            if not login_btn:
                login_btn = self._page.query_selector("button[type='submit']")

            if not login_btn:
                logger.error("Naukri: login button not found")
                return False

            login_btn.click()
            self._human_delay(2500, 4000)

            # Confirm login success — check we're off the login page
            if "login" not in self._page.url.lower():
                return True

            # Also accept if profile/dashboard elements are present
            profile_el = self._page.query_selector(
                ".nI-gNb-pm__icon, .view-resume-btn, [class*='profile'], [class*='dashboard']"
            )
            if profile_el:
                return True

            logger.warning(f"Naukri: login unclear — URL is {self._page.url}")
            return False

        except Exception as e:
            logger.error(f"Naukri login error: {e}")
            return False

    # ── Apply ──────────────────────────────────────────────────────────────────

    def apply(self, job: dict, cover_letter: str) -> tuple[bool, str]:
        url = str(job.get("url", ""))
        try:
            self._page.goto(url, timeout=30000)
            self._human_delay(2000, 3000)

            # Check for external redirect (some Naukri jobs link to company ATS)
            if "naukri.com" not in self._page.url:
                return False, "external_ats"

            # Find the primary apply button
            apply_btn = self._find_apply_button()
            if not apply_btn:
                return False, "no_apply_button"

            btn_id = apply_btn.get_attribute("id") or ""

            # If it's the "login to apply" button, we need to click it to trigger the
            # login-then-return flow, or simply signal login is required
            if "login" in btn_id.lower():
                return False, "not_logged_in"

            apply_btn.click()
            self._human_delay(2000, 3500)

            # Handle post-click state — Naukri may show a modal or quick-apply form
            success = self._handle_apply_modal(cover_letter)
            if success:
                return True, ""

            # Check page content for success signals without modal interaction
            page_text = (self._page.content() or "").lower()
            if any(w in page_text for w in [
                "application sent", "successfully applied", "applied successfully",
                "thank you for applying", "your application", "already applied",
            ]):
                return True, ""

            return False, "submission_unclear"

        except Exception as e:
            logger.error(f"Naukri apply error for {url}: {e}")
            return False, str(e)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _find_apply_button(self):
        # Priority order: logged-in apply → login-to-apply → register
        for sel in [
            "#apply-button",
            "[id*='apply-button']",
            ".apply-button",
            "[class*='applyBtn']",
            "#login-apply-button",
            "[id*='login-apply']",
        ]:
            try:
                el = self._page.query_selector(sel)
                if el and el.is_visible():
                    return el
            except Exception:
                pass

        # Text-based fallback
        try:
            for el in self._page.query_selector_all("button, a"):
                text = (el.inner_text() or "").strip().lower()
                if text in ("apply", "apply now", "login to apply"):
                    if el.is_visible():
                        return el
        except Exception:
            pass

        return None

    def _handle_apply_modal(self, cover_letter: str) -> bool:
        """Handle any apply modal or quick-apply form that appears after clicking Apply."""
        # Wait briefly for modal to render
        self._human_delay(800, 1500)

        # Fill cover letter / message field if present
        if cover_letter:
            for sel in [
                "textarea[name='message']",
                "textarea[placeholder*='cover']",
                "textarea[placeholder*='message']",
                "textarea[placeholder*='why']",
                "textarea",
            ]:
                try:
                    el = self._page.query_selector(sel)
                    if el and el.is_visible():
                        current = (el.input_value() or "").strip()
                        if not current:
                            el.click()
                            el.fill(cover_letter)
                        break
                except Exception:
                    pass

        self._human_delay(500, 1000)

        # Submit the modal form
        for sel in [
            "button.applyBtn",
            "button[id*='apply']",
            "button[class*='apply']",
            "button[type='submit']",
            "button.btn-primary",
        ]:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    text = (btn.inner_text() or "").strip().lower()
                    # Avoid clicking general "Apply Now" page buttons again
                    if text in ("apply", "apply now", "submit application", "confirm apply", "send application"):
                        btn.click()
                        self._human_delay(1500, 2500)
                        return True
            except Exception:
                pass

        # If no modal appeared, a direct quick-apply may have already fired
        page_text = (self._page.content() or "").lower()
        return any(w in page_text for w in [
            "application sent", "successfully applied", "already applied",
            "thank you for applying", "application submitted",
        ])
