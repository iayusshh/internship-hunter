"""
Base class for all platform appliers.
Provides Playwright setup, human-like interaction helpers, and the ABC interface.
"""

import random
import time
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BasePlatformApplier(ABC):
    PLATFORM: str = ""

    def __init__(self, profile: dict, headless: bool = True):
        self.profile  = profile
        self.headless = headless
        self._pw      = None
        self._browser = None
        self._page    = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw      = sync_playwright().start()
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
        # Mask automation fingerprint
        self._page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});"
        )

    def stop(self) -> None:
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ── Human-like helpers ─────────────────────────────────────────────────────

    def _human_delay(self, min_ms: int = 500, max_ms: int = 2000) -> None:
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def _type_human(self, selector: str, text: str, clear: bool = True) -> None:
        self._page.click(selector)
        if clear:
            self._page.keyboard.press("Control+a")
            self._page.keyboard.press("Delete")
        for ch in text:
            self._page.keyboard.type(ch, delay=random.randint(30, 100))
        self._human_delay(100, 300)

    def _click_human(self, selector: str) -> None:
        self._human_delay(200, 600)
        self._page.click(selector)
        self._human_delay(300, 800)

    def _fill_if_empty(self, selector: str, value: str) -> bool:
        """Fill a field only if it's currently empty. Returns True if filled."""
        try:
            el = self._page.query_selector(selector)
            if el and not (el.input_value() or "").strip():
                self._type_human(selector, value, clear=False)
                return True
        except Exception:
            pass
        return False

    def _select_option_by_text(self, selector: str, text: str) -> bool:
        """Select a <select> option whose label contains text. Returns True on success."""
        try:
            self._page.select_option(selector, label=text)
            return True
        except Exception:
            pass
        return False

    def _find_element_by_label(self, label_fragment: str) -> str | None:
        """Return a CSS selector for an input/textarea whose label contains label_fragment."""
        try:
            labels = self._page.query_selector_all("label")
            for label in labels:
                if label_fragment.lower() in (label.inner_text() or "").lower():
                    for_attr = label.get_attribute("for")
                    if for_attr:
                        return f"#{for_attr}"
        except Exception:
            pass
        return None

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def login(self) -> bool:
        """Authenticate. Returns True if login succeeded."""
        ...

    @abstractmethod
    def apply(self, job: dict, cover_letter: str) -> tuple[bool, str]:
        """Submit an application. Returns (success, error_message)."""
        ...
