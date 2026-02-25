"""Browser automation for joining online conferences via Playwright.

Supports:
  - Google Meet   (meet.google.com)
  - Zoom          (zoom.us/wc or app.zoom.us)
  - Microsoft Teams (teams.microsoft.com or teams.live.com)
  - Webex         (*.webex.com)
  - Generic       (any web-based conference URL)
"""

import asyncio
import logging
import re
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext

from .config import config

logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    """Return a short platform identifier based on the meeting URL."""
    url_lower = url.lower()
    if "meet.google.com" in url_lower:
        return "google_meet"
    if "zoom.us" in url_lower or "app.zoom.us" in url_lower:
        return "zoom"
    if "teams.microsoft.com" in url_lower or "teams.live.com" in url_lower:
        return "teams"
    if "webex.com" in url_lower:
        return "webex"
    return "generic"


class ConferenceBrowser:
    """Launches a Chromium browser and joins an online conference."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.platform: str = "generic"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Launch the browser with audio/mic permissions pre-granted."""
        self._playwright = await async_playwright().start()

        launch_args = [
            "--use-fake-ui-for-media-stream",   # auto-allow camera/mic prompts
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

        # Create a context that grants microphone + camera permissions
        self._context = await self._browser.new_context(
            permissions=["microphone", "camera", "notifications"],
            ignore_https_errors=True,
        )

        self.page = await self._context.new_page()
        logger.info("Browser started (headless=%s)", self.headless)

    async def stop(self):
        """Close the browser gracefully."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    # ------------------------------------------------------------------
    # Main join entry point
    # ------------------------------------------------------------------

    async def join_meeting(self, url: str, display_name: Optional[str] = None) -> bool:
        """Navigate to *url* and attempt to join the conference.

        Returns True if joined successfully.
        """
        name = display_name or config.bot_display_name
        self.platform = detect_platform(url)
        logger.info("Joining %s meeting as '%s': %s", self.platform, name, url)

        if self.platform == "google_meet":
            return await self._join_google_meet(url, name)
        if self.platform == "zoom":
            return await self._join_zoom(url, name)
        if self.platform == "teams":
            return await self._join_teams(url, name)
        if self.platform == "webex":
            return await self._join_webex(url, name)
        # Fall back to generic — just navigate to the URL
        return await self._join_generic(url, name)

    # ------------------------------------------------------------------
    # Platform-specific join handlers
    # ------------------------------------------------------------------

    async def _join_google_meet(self, url: str, display_name: str) -> bool:
        """Join a Google Meet session."""
        page = self.page

        # Optional: sign into Google first for a better experience
        if config.google_email and config.google_password:
            await self._google_sign_in()

        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # Dismiss cookie / GDPR banners if present
        await self._dismiss_banners()

        # If a name input is shown (guest join), fill it
        try:
            name_input = page.locator(
                'input[placeholder*="name" i], input[aria-label*="name" i]'
            )
            await name_input.wait_for(state="visible", timeout=5_000)
            await name_input.fill(display_name)
            logger.info("Filled guest name field")
        except Exception:
            pass

        # Turn off camera and microphone before joining (stealth mode)
        await self._toggle_media_off_meet()

        # Click the "Ask to join" / "Join now" button
        joined = await self._click_join_button(
            selectors=[
                'button[jsname="Qx7uuf"]',              # "Ask to join"
                'button[data-idom-class*="join" i]',
                'button:has-text("Ask to join")',
                'button:has-text("Join now")',
                'button:has-text("Join")',
            ]
        )
        if joined:
            logger.info("Joined Google Meet — waiting for admission if needed")
            # Wait a moment; if there's a "waiting room" we stay until admitted
            await asyncio.sleep(3)
        return joined

    async def _join_zoom(self, url: str, display_name: str) -> bool:
        """Join a Zoom meeting via the web client."""
        page = self.page

        # Convert zoom.us/j/... URLs to the web-client URL
        web_url = re.sub(r"zoom\.us/j/", "zoom.us/wc/join/", url)
        if "?" in web_url:
            web_url += f"&prefer=1&un={display_name}"
        else:
            web_url += f"?prefer=1&un={display_name}"

        await page.goto(web_url, wait_until="domcontentloaded", timeout=30_000)
        await self._dismiss_banners()

        # Fill the name field if shown
        try:
            name_input = page.locator('input#inputname, input[placeholder*="name" i]')
            await name_input.wait_for(state="visible", timeout=5_000)
            await name_input.fill(display_name)
        except Exception:
            pass

        # Disable mic/video before joining
        try:
            mute_btn = page.locator('button[aria-label*="mute" i], .zm-btn--silent')
            await mute_btn.first.click(timeout=3_000)
        except Exception:
            pass

        joined = await self._click_join_button(
            selectors=[
                'button#joinBtn',
                'button:has-text("Join")',
                'button:has-text("Join Meeting")',
            ]
        )
        return joined

    async def _join_teams(self, url: str, display_name: str) -> bool:
        """Join a Microsoft Teams meeting via browser."""
        page = self.page

        # Add ?launchAgent=false to prefer web client over app redirect
        sep = "&" if "?" in url else "?"
        web_url = url + sep + "launchAgent=false"

        await page.goto(web_url, wait_until="domcontentloaded", timeout=30_000)
        await self._dismiss_banners()

        # Teams may ask: "Continue on this browser" or "Join on the web"
        try:
            web_btn = page.locator(
                'a:has-text("Continue on this browser")',
                'button:has-text("Join on the web")',
            )
            await web_btn.first.click(timeout=5_000)
        except Exception:
            pass

        # Fill the name input if not signed in
        try:
            name_input = page.locator('input[data-tid="prejoin-display-name-input"]')
            await name_input.wait_for(state="visible", timeout=8_000)
            await name_input.fill(display_name)
        except Exception:
            pass

        # Turn off audio/video before joining
        try:
            toggle_audio = page.locator('[data-tid="toggle-av"]').first
            if await toggle_audio.is_visible(timeout=3_000):
                await toggle_audio.click()
        except Exception:
            pass

        joined = await self._click_join_button(
            selectors=[
                'button[data-tid="prejoin-join-button"]',
                'button:has-text("Join now")',
                'button:has-text("Join")',
            ]
        )
        return joined

    async def _join_webex(self, url: str, display_name: str) -> bool:
        """Join a Cisco Webex meeting via browser."""
        page = self.page
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await self._dismiss_banners()

        try:
            name_input = page.locator('input#guest-name, input[placeholder*="name" i]')
            await name_input.wait_for(state="visible", timeout=5_000)
            await name_input.fill(display_name)
        except Exception:
            pass

        joined = await self._click_join_button(
            selectors=[
                'button#btn-join',
                'button:has-text("Join meeting")',
                'button:has-text("Join")',
            ]
        )
        return joined

    async def _join_generic(self, url: str, display_name: str) -> bool:
        """Generic fallback — just navigate and attempt common join patterns."""
        page = self.page
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await self._dismiss_banners()

        try:
            name_input = page.locator('input[placeholder*="name" i]').first
            if await name_input.is_visible(timeout=3_000):
                await name_input.fill(display_name)
        except Exception:
            pass

        joined = await self._click_join_button(
            selectors=[
                'button:has-text("Join")',
                'button:has-text("Enter")',
                'button:has-text("Start")',
            ]
        )
        return joined

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _click_join_button(self, selectors: list[str]) -> bool:
        """Try each selector in order; click the first visible one."""
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                await btn.wait_for(state="visible", timeout=5_000)
                await btn.click()
                logger.info("Clicked join button: %s", sel)
                return True
            except Exception:
                continue
        logger.warning("Could not find a join button")
        return False

    async def _toggle_media_off_meet(self):
        """Mute camera and mic on the Google Meet pre-join screen."""
        try:
            cam_btn = self.page.locator('[data-is-muted="false"][aria-label*="camera" i]')
            if await cam_btn.is_visible(timeout=2_000):
                await cam_btn.click()
        except Exception:
            pass
        try:
            mic_btn = self.page.locator('[data-is-muted="false"][aria-label*="microphone" i]')
            if await mic_btn.is_visible(timeout=2_000):
                await mic_btn.click()
        except Exception:
            pass

    async def _dismiss_banners(self):
        """Dismiss common cookie/GDPR/notification banners."""
        dismiss_selectors = [
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("I agree")',
            'button:has-text("Got it")',
            'button:has-text("Dismiss")',
            'button:has-text("Close")',
            '[aria-label="Close"]',
        ]
        for sel in dismiss_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=1_000):
                    await btn.click()
                    await asyncio.sleep(0.3)
            except Exception:
                pass

    async def _google_sign_in(self):
        """Sign into a Google account before joining the Meet."""
        page = self.page
        logger.info("Signing into Google as %s", config.google_email)
        try:
            await page.goto("https://accounts.google.com/signin", timeout=20_000)
            await page.fill('input[type="email"]', config.google_email)
            await page.click('#identifierNext')
            await page.wait_for_selector('input[type="password"]', timeout=10_000)
            await page.fill('input[type="password"]', config.google_password)
            await page.click('#passwordNext')
            await page.wait_for_load_state("networkidle", timeout=15_000)
            logger.info("Google sign-in complete")
        except Exception as exc:
            logger.warning("Google sign-in failed: %s", exc)

    async def is_in_meeting(self) -> bool:
        """Heuristic check: are we still in an active conference tab?"""
        if not self.page:
            return False
        try:
            url = self.page.url
            indicators = [
                "meet.google.com",
                "zoom.us/wc",
                "teams.microsoft.com/",
                "teams.live.com/",
                "webex.com/meet",
            ]
            return any(ind in url for ind in indicators)
        except Exception:
            return False
