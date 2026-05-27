"""
LinkedIn Easy Apply automation.
Handles multi-step modal forms, resume upload, cover letter, and common Q&A fields.
"""

import os
import logging
import time

from .base_applier import BasePlatformApplier

logger = logging.getLogger(__name__)


class LinkedInApplier(BasePlatformApplier):
    PLATFORM = "LinkedIn"

    # ── Login ──────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        email    = os.environ.get("LINKEDIN_EMAIL", "")
        password = os.environ.get("LINKEDIN_PASSWORD", "")
        if not email or not password:
            logger.warning("LinkedIn: LINKEDIN_EMAIL or LINKEDIN_PASSWORD not set")
            return False

        try:
            self._page.goto("https://www.linkedin.com/login", timeout=30000)
            self._human_delay(800, 1500)

            self._type_human("input#username", email)
            self._human_delay(300, 600)
            self._type_human("input#password", password)
            self._human_delay(400, 800)

            self._page.click("button[type='submit']")
            self._human_delay(2000, 4000)

            # Handle 2FA — wait up to 90 s for user to complete in non-headless mode
            if "checkpoint" in self._page.url or "challenge" in self._page.url:
                if not self.headless:
                    logger.info("LinkedIn: 2FA detected — waiting up to 90s for manual completion")
                    deadline = time.time() + 90
                    while time.time() < deadline:
                        if "feed" in self._page.url or "jobs" in self._page.url:
                            break
                        time.sleep(2)
                else:
                    logger.warning("LinkedIn: 2FA in headless mode — cannot proceed")
                    return False

            if "feed" in self._page.url or "mynetwork" in self._page.url:
                return True
            if "linkedin.com" in self._page.url and "login" not in self._page.url:
                return True
            logger.warning(f"LinkedIn: login unclear — URL is {self._page.url}")
            return False

        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            return False

    # ── Apply ──────────────────────────────────────────────────────────────────

    def apply(self, job: dict, cover_letter: str) -> tuple[bool, str]:
        url = str(job.get("url", ""))
        try:
            self._page.goto(url, timeout=30000)
            self._human_delay(1500, 3000)

            # Find Easy Apply button
            easy_apply = self._find_easy_apply_button()
            if not easy_apply:
                return False, "no_easy_apply"

            easy_apply.click()
            self._human_delay(1000, 2000)

            # Step through the modal
            max_steps = 10
            for step in range(max_steps):
                if not self._modal_visible():
                    break

                self._fill_modal_step(cover_letter)
                self._human_delay(500, 1000)

                # Check for submit button first
                if self._try_submit():
                    self._human_delay(1500, 3000)
                    # Confirm dismissal
                    self._dismiss_post_apply_modal()
                    return True, ""

                # Check for "Review" step
                if self._try_review():
                    continue

                # Advance to next step
                if not self._try_next():
                    return False, "stuck_in_modal"

            # Final submit attempt after loop
            if self._try_submit():
                self._human_delay(1500, 2500)
                self._dismiss_post_apply_modal()
                return True, ""

            return False, "modal_did_not_complete"

        except Exception as e:
            logger.error(f"LinkedIn apply error for {url}: {e}")
            return False, str(e)

    # ── Modal helpers ──────────────────────────────────────────────────────────

    def _find_easy_apply_button(self):
        selectors = [
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            "button[data-job-id]",
        ]
        for sel in selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    return btn
            except Exception:
                pass
        # Text search fallback
        try:
            btns = self._page.query_selector_all("button")
            for b in btns:
                if "easy apply" in (b.inner_text() or "").lower():
                    return b
        except Exception:
            pass
        return None

    def _modal_visible(self) -> bool:
        for sel in [".jobs-easy-apply-modal", ".artdeco-modal", "[role='dialog']"]:
            try:
                el = self._page.query_selector(sel)
                if el and el.is_visible():
                    return True
            except Exception:
                pass
        return False

    def _fill_modal_step(self, cover_letter: str) -> None:
        profile = self.profile
        answers = profile.get("common_answers", {})

        # Phone number
        for sel in ["input[id*='phoneNumber']", "input[name*='phoneNumber']", "input[type='tel']"]:
            self._fill_if_empty(sel, profile.get("phone", ""))

        # Cover letter textarea
        for sel in ["textarea[id*='cover']", "textarea[name*='cover']", ".jobs-easy-apply-form-section__cover-letter textarea"]:
            try:
                el = self._page.query_selector(sel)
                if el and el.is_visible():
                    current = (el.input_value() or "").strip()
                    if not current and cover_letter:
                        self._type_human(sel, cover_letter)
                    break
            except Exception:
                pass

        # Handle radio groups and generic questions
        self._answer_common_questions(answers)

        # Resume — prefer existing uploaded resume, don't re-upload every time
        self._handle_resume_step(profile.get("resume_path", ""))

    def _answer_common_questions(self, answers: dict) -> None:
        """Fill known Q&A patterns in the modal."""
        label_answer_map = {
            "years of experience":     str(self.profile.get("years_experience", "0")),
            "year":                    str(self.profile.get("years_experience", "0")),
            "authorized":              "Yes",
            "legally authorized":      "Yes",
            "sponsorship":             "No",
            "require visa":            "No",
            "start date":              answers.get("availability", "Immediately"),
            "when can you start":      answers.get("availability", "Immediately"),
            "availability":            answers.get("availability", "Immediately"),
            "willing to relocate":     "Yes" if answers.get("willing_to_relocate") else "No",
            "city":                    "",  # skip
            "salary":                  self.profile.get("expected_stipend", ""),
        }

        try:
            inputs = self._page.query_selector_all(".jobs-easy-apply-form-element")
            for elem in inputs:
                try:
                    label_text = (elem.query_selector("label, legend") or elem).inner_text().lower()
                    for keyword, answer in label_answer_map.items():
                        if keyword in label_text and answer:
                            # Try text input
                            inp = elem.query_selector("input[type='text'], input[type='number']")
                            if inp and inp.is_visible() and not (inp.input_value() or "").strip():
                                self._type_human_el(inp, answer)
                                break
                            # Try select
                            sel = elem.query_selector("select")
                            if sel and sel.is_visible():
                                try:
                                    self._page.select_option(
                                        f"#{sel.get_attribute('id') or ''}", label=answer
                                    )
                                except Exception:
                                    pass
                                break
                            # Try radio buttons
                            radios = elem.query_selector_all("input[type='radio']")
                            for r in radios:
                                try:
                                    lbl = self._page.query_selector(f"label[for='{r.get_attribute('id')}']")
                                    if lbl and answer.lower() in (lbl.inner_text() or "").lower():
                                        r.click()
                                        break
                                except Exception:
                                    pass
                            break
                except Exception:
                    pass
        except Exception:
            pass

    def _type_human_el(self, el, text: str) -> None:
        el.click()
        self._page.keyboard.press("Control+a")
        self._page.keyboard.press("Delete")
        import random
        for ch in text:
            self._page.keyboard.type(ch, delay=random.randint(30, 100))

    def _handle_resume_step(self, resume_path: str) -> None:
        """Upload resume if prompted and path is set."""
        if not resume_path or not os.path.exists(resume_path):
            return
        try:
            upload = self._page.query_selector("input[type='file']")
            if upload and upload.is_visible():
                upload.set_input_files(resume_path)
                self._human_delay(1000, 2000)
        except Exception:
            pass

    def _try_next(self) -> bool:
        next_selectors = [
            "button[aria-label='Continue to next step']",
            "button[aria-label*='Next']",
            "footer button:not([aria-label*='Dismiss']):not([aria-label*='Close'])",
        ]
        for sel in next_selectors:
            try:
                btns = self._page.query_selector_all(sel)
                for btn in btns:
                    label = (btn.get_attribute("aria-label") or btn.inner_text() or "").lower()
                    if "dismiss" in label or "close" in label or "discard" in label:
                        continue
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        self._human_delay(600, 1200)
                        return True
            except Exception:
                pass
        return False

    def _try_review(self) -> bool:
        try:
            review_btn = self._page.query_selector("button[aria-label='Review your application']")
            if review_btn and review_btn.is_visible():
                review_btn.click()
                self._human_delay(600, 1200)
                return True
        except Exception:
            pass
        return False

    def _try_submit(self) -> bool:
        submit_selectors = [
            "button[aria-label='Submit application']",
            "button[aria-label*='Submit']",
        ]
        for sel in submit_selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    btn.click()
                    return True
            except Exception:
                pass
        # Text search fallback
        try:
            btns = self._page.query_selector_all("footer button, .jobs-easy-apply-modal button")
            for b in btns:
                text = (b.inner_text() or "").lower().strip()
                if text == "submit application" or text == "submit":
                    if b.is_visible() and b.is_enabled():
                        b.click()
                        return True
        except Exception:
            pass
        return False

    def _dismiss_post_apply_modal(self) -> None:
        try:
            dismiss = self._page.query_selector("button[aria-label='Dismiss']")
            if dismiss and dismiss.is_visible():
                dismiss.click()
        except Exception:
            pass
