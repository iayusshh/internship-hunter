"""
Unstop applier — hackathon registration via Playwright.
Credentials: UNSTOP_EMAIL, UNSTOP_PASSWORD (env vars).
"""

import os
import logging

from .base_applier import BasePlatformApplier

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://unstop.com/login"


class UnstopApplier(BasePlatformApplier):
    PLATFORM = "Unstop Hackathons"

    def login(self) -> bool:
        email    = os.environ.get("UNSTOP_EMAIL", "")
        password = os.environ.get("UNSTOP_PASSWORD", "")
        if not email or not password:
            logger.error("UNSTOP_EMAIL / UNSTOP_PASSWORD not set in environment")
            return False
        try:
            self._page.goto(_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
            self._human_delay(1000, 2000)

            email_sel = "input[type='email'], input[name='email'], input[placeholder*='mail' i]"
            self._page.wait_for_selector(email_sel, timeout=10000)
            self._type_human(email_sel, email)
            self._type_human("input[type='password']", password)
            self._human_delay(500, 1000)

            submit = self._page.query_selector("button[type='submit']")
            if submit:
                submit.click()
            else:
                self._page.keyboard.press("Enter")

            self._page.wait_for_load_state("domcontentloaded", timeout=15000)
            self._human_delay(1500, 2500)

            if "/login" in self._page.url:
                logger.error("Unstop login: still on login page after submit — check credentials")
                return False

            logger.info("Unstop login successful")
            return True
        except Exception as e:
            logger.error(f"Unstop login error: {e}")
            return False

    def apply(self, job: dict, cover_letter: str = "") -> tuple[bool, str]:
        url = job.get("url", "")
        if not url:
            return False, "no_url"

        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
            self._human_delay(1500, 2500)

            # Try to click the main register/apply CTA
            register_selectors = [
                "button:has-text('Register Now')",
                "button:has-text('Register')",
                "button:has-text('Apply Now')",
                "a:has-text('Register Now')",
                "a:has-text('Register')",
                "[class*='register-btn']",
                "[class*='apply-btn']",
            ]
            clicked = False
            for sel in register_selectors:
                try:
                    btn = self._page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        clicked = True
                        self._human_delay(1500, 2500)
                        break
                except Exception:
                    continue

            if not clicked:
                return False, "register_button_not_found"

            # Fill team name if prompted
            team_name_sel = "input[placeholder*='team' i], input[name*='team' i]"
            try:
                el = self._page.query_selector(team_name_sel)
                if el and el.is_visible():
                    first_name = self.profile.get("full_name", "Team").split()[0]
                    self._type_human(team_name_sel, f"{first_name}'s Team")
                    self._human_delay(300, 600)
            except Exception:
                pass

            # Submit registration
            final_submit_sel = "button[type='submit'], button:has-text('Submit'), button:has-text('Confirm')"
            try:
                btn = self._page.query_selector(final_submit_sel)
                if btn and btn.is_visible():
                    btn.click()
                    self._human_delay(1500, 2000)
            except Exception:
                pass

            logger.info(f"Unstop: registered for {job.get('title', url)}")
            return True, ""

        except Exception as e:
            logger.error(f"Unstop apply error for {url}: {e}")
            return False, str(e)[:120]
