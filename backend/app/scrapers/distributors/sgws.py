"""
ABVTrends - Southern Glazer's Wine & Spirits (SGWS Proof) Scraper

Scrapes product data from SGWS Proof portal (shop.sgproof.com).

SGWS Proof is the B2B e-commerce platform for Southern Glazer's Wine & Spirits,
the largest wine and spirits distributor in North America.

API Discovery Notes:
- Base URL: https://shop.sgproof.com
- Search URL: /search?text=&f-category=Spirits
- Product URLs: /sgws/en/usd/{PRODUCT-NAME}/p/{SKU}
- Uses Hybris/SAP Commerce Cloud backend
"""

import asyncio
import logging
import random
import re
from typing import Any, Optional
from urllib.parse import quote, urlencode

from app.scrapers.distributors.base import BaseDistributorScraper, RawProduct
from app.scrapers.utils.stealth_context import StealthContextFactory

logger = logging.getLogger(__name__)


class SGWSScraper(BaseDistributorScraper):
    """
    Scraper for Southern Glazer's Wine & Spirits Proof portal.

    SGWS Proof provides wholesale pricing and ordering for licensed
    retailers. Products include spirits, wine, beer, and RTD beverages.
    """

    name = "sgws"
    base_url = "https://shop.sgproof.com"

    # Categories to scrape with their filter values
    CATEGORIES = [
        {"name": "spirits", "filter": "Spirits", "id": "spirits"},
        {"name": "wine", "filter": "Wine", "id": "wine"},
        {"name": "beer", "filter": "Beer", "id": "beer"},
        {"name": "rtd", "filter": "Ready to Drink", "id": "rtd"},
    ]

    # Subcategories for more granular scraping
    SPIRIT_SUBCATEGORIES = [
        "Vodka", "Whiskey", "Tequila", "Rum", "Gin", "Brandy",
        "Cognac", "Mezcal", "Liqueur", "Cordial",
    ]

    def __init__(self, credentials: dict[str, Any]):
        """
        Initialize SGWS scraper.

        Args:
            credentials: Dict with:
                - email: Login email
                - password: Login password
                - account_id: SGWS account number (e.g., "102376")
                - session_cookies: Pre-existing cookies dict (optional)
        """
        super().__init__(credentials)
        self.account_id = credentials.get("account_id", "")
        self.session_cookies = credentials.get("session_cookies", {})
        # Store Playwright cookies in proper format for reuse
        self._playwright_cookies: list[dict] = []

    async def authenticate(self) -> bool:
        """
        Authenticate with SGWS Proof.

        SGWS uses a complex auth flow with multiple cookies. For now,
        we'll use Playwright to capture session cookies after manual login.

        Returns:
            True if authentication successful
        """
        # Try to load saved cookies from manual capture first
        if not self.session_cookies:
            try:
                from app.scrapers.utils.cookie_capture import load_saved_cookies, cookies_to_dict
                saved_cookies = load_saved_cookies("sgws")
                if saved_cookies:
                    self.session_cookies = cookies_to_dict(saved_cookies)
                    self._playwright_cookies = saved_cookies
                    logger.info(f"Loaded {len(saved_cookies)} saved cookies for SGWS")
            except Exception as e:
                logger.debug(f"Could not load saved cookies: {e}")

        # Check if we have pre-captured session cookies
        if self.session_cookies:
            for name, value in self.session_cookies.items():
                self.session.cookies.set(name, value, domain="shop.sgproof.com")

            # Set common headers for authenticated requests
            self.session.headers.update({
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/search",
            })

            # Verify session is valid by making a test request
            try:
                response = await self.session.get(
                    f"{self.base_url}/sgws/en/usd/search",
                    params={"text": "", "f-category": "Spirits"},
                )
                if response.status_code == 200:
                    # Check if response contains login indicators (session expired)
                    response_text = response.text
                    if "Sign up to view product prices" in response_text or 'href="/login"' in response_text:
                        logger.warning("SGWS cookies expired - page shows login prompts")
                        # Clear invalid cookies
                        try:
                            from app.scrapers.utils.cookie_capture import COOKIES_DIR
                            cookie_file = COOKIES_DIR / "sgws_cookies.json"
                            if cookie_file.exists():
                                cookie_file.unlink()
                                logger.info("Deleted expired cookies file")
                        except Exception:
                            pass
                        self.session_cookies = {}
                        self._playwright_cookies = []
                    else:
                        logger.info("SGWS session validated successfully")
                        self.authenticated = True
                        return True
                else:
                    logger.warning(f"SGWS session check failed: {response.status_code}")
            except Exception as e:
                logger.error(f"SGWS session verification failed: {e}")

        # Try Playwright-based login
        try:
            cookies = await self._login_with_playwright()
            if cookies:
                for name, value in cookies.items():
                    self.session.cookies.set(name, value, domain=".sgproof.com")

                # Also add critical headers for SGWS API
                self.session.headers.update({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                })

                logger.info(f"Set {len(cookies)} cookies on httpx session")
                self.authenticated = True
                return True
        except Exception as e:
            logger.error(f"Playwright login failed: {e}")

        logger.warning("SGWS authentication failed")
        return False

    async def _handle_age_verification(self, page) -> None:
        """
        Handle SGWS age verification popup.

        SGWS shows a modal with:
        1. A "Select Site" dropdown (must select a site first)
        2. A "Were you born before [date]?" question with Yes/No buttons
        """
        try:
            await asyncio.sleep(2)  # Wait for modal to fully render

            # Step 0: Handle cookie consent banner first (can block other clicks)
            try:
                cookie_btn = page.locator('button:has-text("Accept All")').first
                if await cookie_btn.count() > 0 and await cookie_btn.is_visible(timeout=2000):
                    await cookie_btn.click()
                    logger.info("Clicked 'Accept All' for cookie consent")
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Step 1: Handle "Select Site" dropdown - REQUIRED before Yes button works
            # Prefer CA - South for California accounts (Santee is in Southern CA)
            preferred_sites = ["CA - South", "CA-South", "CA South", "California - South", "CA"]

            try:
                # Try multiple selectors for the site dropdown
                dropdown_selectors = [
                    'select.verify-select-input',
                    'select.form-select-input',
                    'select[aria-label*="site" i]',
                    '.verify-select select',
                    'select',
                ]

                site_selected = False
                for dropdown_sel in dropdown_selectors:
                    try:
                        site_dropdown = page.locator(dropdown_sel).first
                        if await site_dropdown.count() > 0 and await site_dropdown.is_visible(timeout=2000):
                            logger.info(f"Found site dropdown with selector: {dropdown_sel}")
                            # Get all options
                            options = await site_dropdown.locator("option").all()
                            logger.info(f"Dropdown has {len(options)} options")

                            # First pass: look for preferred CA site
                            for opt in options:
                                val = await opt.get_attribute("value")
                                text = (await opt.text_content() or "").strip()
                                disabled = await opt.get_attribute("disabled")

                                if disabled or not val or not val.strip():
                                    continue

                                # Check if this is a preferred site
                                for pref in preferred_sites:
                                    if pref.lower() in text.lower() or text.lower() in pref.lower():
                                        await site_dropdown.select_option(value=val)
                                        logger.info(f"Selected preferred site: {text} (value={val})")
                                        site_selected = True
                                        await asyncio.sleep(1)
                                        break
                                if site_selected:
                                    break

                            # Second pass: if no preferred site found, select first valid option
                            if not site_selected:
                                for opt in options:
                                    val = await opt.get_attribute("value")
                                    text = (await opt.text_content() or "").strip()
                                    disabled = await opt.get_attribute("disabled")
                                    if val and val.strip() and not disabled and "select" not in text.lower():
                                        await site_dropdown.select_option(value=val)
                                        logger.info(f"Selected fallback site: {text} (value={val})")
                                        site_selected = True
                                        await asyncio.sleep(1)
                                        break

                            if site_selected:
                                break
                    except Exception as e:
                        logger.debug(f"Dropdown selector {dropdown_sel} failed: {e}")
                        continue

                if not site_selected:
                    # Try JavaScript as fallback for dropdown - prefer CA - South
                    try:
                        selected = await page.evaluate('''
                            () => {
                                const select = document.querySelector('select.verify-select-input, select.form-select-input, select');
                                if (select && select.options.length > 1) {
                                    // First look for CA - South
                                    const preferred = ["CA - South", "CA-South", "CA South", "California"];
                                    for (const pref of preferred) {
                                        for (let i = 0; i < select.options.length; i++) {
                                            const optText = select.options[i].text || "";
                                            if (!select.options[i].disabled && optText.toLowerCase().includes(pref.toLowerCase())) {
                                                select.selectedIndex = i;
                                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                                return select.options[i].text;
                                            }
                                        }
                                    }
                                    // Fallback to first valid option
                                    for (let i = 0; i < select.options.length; i++) {
                                        if (!select.options[i].disabled && select.options[i].value) {
                                            select.selectedIndex = i;
                                            select.dispatchEvent(new Event('change', { bubbles: true }));
                                            return select.options[i].text;
                                        }
                                    }
                                }
                                return null;
                            }
                        ''')
                        if selected:
                            logger.info(f"Selected site via JavaScript: {selected}")
                            await asyncio.sleep(1)
                    except Exception as e:
                        logger.debug(f"JavaScript dropdown selection failed: {e}")

            except Exception as e:
                logger.warning(f"Site dropdown handling failed: {e}")

            # Step 2: Click "Yes" button for age verification
            yes_button_selectors = [
                # Exact text match buttons
                'button:text-is("Yes")',
                'button:has-text("Yes")',
                # Look near the age question text
                'button:near(:text("born before"))',
                # Generic fallbacks
                'a:has-text("Yes")',
                'input[value="Yes"]',
                '[role="button"]:has-text("Yes")',
            ]

            for selector in yes_button_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=2000):
                        await btn.click()
                        logger.info(f"Clicked 'Yes' button: {selector}")
                        await asyncio.sleep(3)  # Wait for page to load after verification
                        return
                except Exception as e:
                    logger.debug(f"Yes button selector {selector} failed: {e}")
                    continue

            # Fallback: Find all visible buttons and click one that says "Yes"
            try:
                all_buttons = page.locator('button:visible')
                btn_count = await all_buttons.count()
                logger.info(f"Checking {btn_count} visible buttons for 'Yes'")
                for i in range(btn_count):
                    btn = all_buttons.nth(i)
                    btn_text = await btn.text_content()
                    logger.debug(f"Button {i}: '{btn_text}'")
                    if btn_text and "yes" in btn_text.strip().lower():
                        await btn.click()
                        logger.info(f"Clicked visible button: '{btn_text}'")
                        await asyncio.sleep(3)
                        return
            except Exception as e:
                logger.debug(f"Fallback button search failed: {e}")

            # Last resort: Use JavaScript to find and click the Yes button
            try:
                clicked = await page.evaluate('''
                    () => {
                        // Find all clickable elements
                        const elements = document.querySelectorAll('button, a, [role="button"], [onclick]');
                        for (const el of elements) {
                            const text = el.textContent || el.innerText || '';
                            if (text.trim().toLowerCase() === 'yes') {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }
                ''')
                if clicked:
                    logger.info("Clicked 'Yes' via JavaScript")
                    await asyncio.sleep(3)
                    return
            except Exception as e:
                logger.debug(f"JavaScript click failed: {e}")

            logger.info("Age verification handling complete (no Yes button found)")

        except Exception as e:
            logger.debug(f"Age verification handling error (may be expected): {e}")

    async def _handle_recaptcha_checkbox(self, page) -> bool:
        """
        Attempt to click the reCAPTCHA "I'm not a robot" checkbox.

        reCAPTCHA v2 checkbox is in an iframe. With stealth mode and good IP
        reputation, clicking the checkbox may pass without a challenge.

        Returns:
            True if checkbox was clicked, False otherwise
        """
        try:
            logger.info("Looking for reCAPTCHA checkbox...")

            # reCAPTCHA is in an iframe
            recaptcha_frame_selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[title*="reCAPTCHA"]',
                'iframe[name*="recaptcha"]',
            ]

            for frame_selector in recaptcha_frame_selectors:
                try:
                    frame_elem = page.frame_locator(frame_selector).first
                    # The checkbox is a div with class "recaptcha-checkbox-border"
                    checkbox = frame_elem.locator('.recaptcha-checkbox-border, #recaptcha-anchor')

                    if await checkbox.count() > 0:
                        logger.info(f"Found reCAPTCHA checkbox in frame: {frame_selector}")
                        await checkbox.click(timeout=5000)
                        logger.info("Clicked reCAPTCHA checkbox")

                        # Wait to see if challenge appears or it passes
                        await asyncio.sleep(3)

                        # Check if we passed (checkbox gets checkmark)
                        try:
                            checked = frame_elem.locator('[aria-checked="true"], .recaptcha-checkbox-checked')
                            if await checked.count() > 0:
                                logger.info("reCAPTCHA passed without challenge!")
                                return True
                            else:
                                logger.warning("reCAPTCHA challenge appeared - may need manual solving or 2Captcha")
                        except Exception:
                            pass

                        return True
                except Exception as e:
                    logger.debug(f"Frame selector {frame_selector} failed: {e}")
                    continue

            # Fallback: try to find checkbox by role/class outside iframe
            try:
                checkbox_selectors = [
                    '.g-recaptcha',
                    '[data-sitekey]',
                    '#recaptcha-anchor',
                ]
                for selector in checkbox_selectors:
                    elem = page.locator(selector).first
                    if await elem.count() > 0 and await elem.is_visible(timeout=2000):
                        await elem.click(timeout=5000)
                        logger.info(f"Clicked reCAPTCHA element: {selector}")
                        await asyncio.sleep(3)
                        return True
            except Exception:
                pass

            logger.info("No reCAPTCHA checkbox found on this page")
            return False

        except Exception as e:
            logger.debug(f"reCAPTCHA handling error: {e}")
            return False

    async def _handle_popup_dialogs(self, page) -> None:
        """
        Handle promotional/holiday popups that may appear on SGWS.

        These popups (like holiday delivery schedule notices) have a "Close" button.
        """
        try:
            logger.info("Checking for popups...")
            await asyncio.sleep(3)  # Wait for popup to fully render

            # Take screenshot before popup handling for debugging
            await page.screenshot(path="/tmp/sgws_before_popup.png")
            logger.info("Screenshot before popup handling: /tmp/sgws_before_popup.png")

            # Check if holiday popup is present by looking for its content
            holiday_popup_visible = False
            try:
                holiday_text = page.locator('text="HOLIDAY DELIVERY"')
                if await holiday_text.count() > 0:
                    holiday_popup_visible = True
                    logger.info("Holiday delivery popup detected!")
            except Exception:
                pass

            if not holiday_popup_visible:
                logger.info("No popup detected, continuing...")
                return

            # Log all visible buttons for debugging
            try:
                all_btns = await page.locator('button').all()
                logger.info(f"Found {len(all_btns)} total buttons on page")
                for i, btn in enumerate(all_btns[:10]):  # Log first 10
                    try:
                        text = await btn.text_content()
                        visible = await btn.is_visible()
                        logger.info(f"  Button {i}: '{text.strip() if text else 'N/A'}' visible={visible}")
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Could not enumerate buttons: {e}")

            # APPROACH 1: Force click any button containing "Close"
            try:
                close_btn = page.locator('button:has-text("Close")').first
                if await close_btn.count() > 0:
                    logger.info("Found Close button, attempting force click...")
                    await close_btn.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    await close_btn.click(force=True)
                    logger.info("Force clicked Close button!")
                    await asyncio.sleep(1)
                    # Verify popup closed
                    if await page.locator('text="HOLIDAY DELIVERY"').count() == 0:
                        logger.info("Popup successfully closed")
                        return
            except Exception as e:
                logger.debug(f"Force click approach failed: {e}")

            # APPROACH 2: Click by bounding box coordinates
            try:
                close_btn = page.locator('button:has-text("Close")').first
                box = await close_btn.bounding_box()
                if box:
                    x = box['x'] + box['width'] / 2
                    y = box['y'] + box['height'] / 2
                    logger.info(f"Clicking Close button at coordinates ({x}, {y})")
                    await page.mouse.click(x, y)
                    await asyncio.sleep(1)
                    if await page.locator('text="HOLIDAY DELIVERY"').count() == 0:
                        logger.info("Popup closed via coordinate click")
                        return
            except Exception as e:
                logger.debug(f"Coordinate click failed: {e}")

            # APPROACH 3: JavaScript direct click with multiple selectors
            try:
                closed = await page.evaluate('''
                    () => {
                        // Try to find the Close button in various ways
                        const selectors = [
                            'button:contains("Close")',
                            '.modal button',
                            '[role="dialog"] button',
                            'div[class*="modal"] button',
                            'div[class*="popup"] button',
                        ];

                        // First, try direct text match
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            const text = (btn.textContent || '').trim();
                            if (text.toLowerCase() === 'close') {
                                console.log('Found Close button via text match');
                                btn.dispatchEvent(new MouseEvent('click', {
                                    bubbles: true,
                                    cancelable: true,
                                    view: window
                                }));
                                return 'text-match';
                            }
                        }

                        // Try clicking red-styled buttons (SGWS uses red for Close)
                        for (const btn of buttons) {
                            const style = window.getComputedStyle(btn);
                            const bgColor = style.backgroundColor;
                            // Red buttons typically have high R value
                            if (bgColor.includes('rgb') && bgColor.includes('(')) {
                                const text = (btn.textContent || '').trim().toLowerCase();
                                if (text.includes('close')) {
                                    console.log('Found red Close button');
                                    btn.dispatchEvent(new MouseEvent('click', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    }));
                                    return 'red-button';
                                }
                            }
                        }

                        // Try removing modal backdrop
                        const modals = document.querySelectorAll('.modal, [role="dialog"], div[class*="modal"]');
                        for (const modal of modals) {
                            modal.style.display = 'none';
                            console.log('Hidden modal element');
                        }

                        const backdrops = document.querySelectorAll('.modal-backdrop, .overlay, [class*="backdrop"]');
                        for (const bd of backdrops) {
                            bd.style.display = 'none';
                        }

                        return modals.length > 0 ? 'hidden-modal' : null;
                    }
                ''')
                if closed:
                    logger.info(f"JavaScript popup handling result: {closed}")
                    await asyncio.sleep(1)
                    if await page.locator('text="HOLIDAY DELIVERY"').count() == 0:
                        logger.info("Popup closed via JavaScript")
                        return
            except Exception as e:
                logger.debug(f"JavaScript handling failed: {e}")

            # APPROACH 4: Press Escape key
            try:
                logger.info("Trying Escape key...")
                await page.keyboard.press('Escape')
                await asyncio.sleep(1)
                if await page.locator('text="HOLIDAY DELIVERY"').count() == 0:
                    logger.info("Popup closed via Escape key")
                    return
            except Exception as e:
                logger.debug(f"Escape key failed: {e}")

            # APPROACH 5: Click backdrop/overlay to dismiss
            try:
                logger.info("Trying to click modal backdrop...")
                backdrop = page.locator('.modal-backdrop, .overlay, [class*="backdrop"]').first
                if await backdrop.count() > 0:
                    await backdrop.click(force=True, position={"x": 10, "y": 10})
                    await asyncio.sleep(1)
            except Exception as e:
                logger.debug(f"Backdrop click failed: {e}")

            # Take screenshot after all attempts
            await page.screenshot(path="/tmp/sgws_after_popup_attempts.png")
            logger.warning("Could not close popup. Screenshot: /tmp/sgws_after_popup_attempts.png")

        except Exception as e:
            logger.error(f"Popup handling error: {e}")

    async def _login_with_playwright(self) -> Optional[dict[str, str]]:
        """
        Use Playwright to automate login and capture session cookies.

        SGWS Proof uses a single-page login with username and password fields.

        Returns:
            Dict of session cookies or None if login fails
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install")
            return None

        email = self.credentials.get("email")
        password = self.credentials.get("password")

        if not email or not password:
            logger.error("SGWS credentials not provided")
            return None

        cookies_dict = {}

        async with async_playwright() as p:
            # Use headless=False for debugging, set to True for production
            browser = await p.chromium.launch(headless=False)

            # Store browser context for reuse during scraping
            self._playwright = p
            self._browser = browser
            # Use stealth context factory for anti-detection
            context = await StealthContextFactory.create_context(browser)
            page = await context.new_page()

            try:
                # Navigate to login page (use /auth/login for direct login form)
                logger.info("Navigating to SGWS login page...")
                await page.goto(f"{self.base_url}/auth/login", wait_until="networkidle")
                await asyncio.sleep(3)

                # Handle age verification popup if present (dropdown selector)
                await self._handle_age_verification(page)

                # SGWS /auth/login has clean Email Address and Password fields
                logger.info("Filling login form...")

                # Fill username/email field - try multiple selectors
                email_selectors = [
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[placeholder*="Email" i]',
                    'input[aria-label*="Email" i]',
                    'input[id*="email" i]',
                    'input[placeholder*="Username" i]',
                    'input[name="userId"]',
                    'input[name="username"]',
                    'input[type="text"]',
                ]

                email_filled = False
                for selector in email_selectors:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.fill(email, timeout=5000)
                            email_filled = True
                            logger.info(f"Email filled using selector: {selector}")
                            break
                    except Exception:
                        continue

                if not email_filled:
                    logger.error("Could not find email input field")
                    await page.screenshot(path="/tmp/sgws_login_debug.png")
                    await browser.close()
                    return None

                # Fill password field - on same page
                await asyncio.sleep(1)
                logger.info("Filling password...")

                password_selectors = [
                    'input[placeholder*="Password" i]',
                    'input[type="password"]',
                    'input[name="password"]',
                ]

                password_filled = False
                for selector in password_selectors:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.fill(password, timeout=5000)
                            password_filled = True
                            logger.info(f"Password filled using: {selector}")
                            break
                    except Exception as e:
                        logger.debug(f"Password selector {selector} failed: {e}")
                        continue

                if not password_filled:
                    logger.error("Could not find password input field")
                    await page.screenshot(path="/tmp/sgws_password_debug.png")
                    await browser.close()
                    return None

                # Handle reCAPTCHA checkbox if present
                await asyncio.sleep(1)
                await self._handle_recaptcha_checkbox(page)

                # Click Log In button
                await asyncio.sleep(1)
                login_selectors = [
                    'button:has-text("Log in")',  # SGWS uses "Log in" with lowercase 'i'
                    'button:has-text("Log In")',
                    'button:has-text("Login")',
                    'button:has-text("Sign In")',
                    'button[type="submit"]',
                    'input[type="submit"]',
                ]

                login_clicked = False
                for selector in login_selectors:
                    try:
                        elem = page.locator(selector).first
                        if await elem.count() > 0 and await elem.is_visible():
                            await elem.click(timeout=5000)
                            login_clicked = True
                            logger.info(f"Login button clicked using: {selector}")
                            break
                    except Exception:
                        continue

                if not login_clicked:
                    await page.keyboard.press("Enter")
                    logger.info("Pressed Enter to submit")

                # Wait for login to complete
                logger.info("Waiting for login to complete...")
                await asyncio.sleep(10)

                current_url = page.url
                logger.info(f"Current URL after login: {current_url}")

                # Take screenshot for debugging (with longer timeout)
                await page.screenshot(path="/tmp/sgws_login_error.png", timeout=60000)

                # Check if login was successful by looking for DEFINITIVE logged-in indicators
                # IMPORTANT: Must check for NOT-logged-in indicators first, as some elements
                # like "Shop" appear on public site too

                # Check for indicators that user is NOT logged in
                not_logged_in_indicators = [
                    page.locator('text="Sign up to view product prices"'),
                    page.locator('a:has-text("Sign Up")'),
                    page.locator('a:has-text("Log In")'),
                    page.locator('button:has-text("Log In")'),
                    page.locator('text="Create an Account"'),
                ]

                is_not_logged_in = False
                for indicator in not_logged_in_indicators:
                    try:
                        if await indicator.count() > 0 and await indicator.is_visible(timeout=2000):
                            indicator_text = await indicator.first.text_content()
                            logger.warning(f"Found NOT-logged-in indicator: '{indicator_text}'")
                            is_not_logged_in = True
                            break
                    except Exception:
                        continue

                if is_not_logged_in:
                    logger.error("Login failed - site shows login/signup buttons (reCAPTCHA likely blocked)")
                    await page.screenshot(path="/tmp/sgws_login_failed.png")
                    await browser.close()
                    return None

                # Check for DEFINITIVE logged-in indicators
                # The page shows "Acct: XXXXX" when logged in, or user's name/account menu
                account_indicator = page.locator('text=/Acct[:\.]?\s*\d+/i')
                my_account_link = page.locator('a:has-text("My Account"), a:has-text("Account")')
                logout_link = page.locator('a:has-text("Log Out"), a:has-text("Logout"), button:has-text("Log Out")')

                is_logged_in = False
                for indicator in [account_indicator, my_account_link, logout_link]:
                    try:
                        if await indicator.count() > 0:
                            indicator_text = await indicator.first.text_content()
                            logger.info(f"Found logged-in indicator: '{indicator_text}'")
                            is_logged_in = True
                            break
                    except Exception:
                        continue

                if is_logged_in:
                    logger.info("Login successful - definitive account indicators found")
                elif "/login" in current_url.lower() or "/auth" in current_url.lower():
                    # Still on login page - check for error
                    error_elem = page.locator('.error, .alert-danger, [class*="error"]')
                    if await error_elem.count() > 0:
                        error_text = await error_elem.first.text_content()
                        logger.error(f"Login error: {error_text}")
                    logger.error("Login failed - still on login page")
                    await browser.close()
                    return None
                else:
                    # Not on login page - check if NOT logged in by looking for login/signup buttons
                    await page.screenshot(path="/tmp/sgws_login_check.png")

                    # If no login/signup buttons visible, assume logged in
                    login_btn = page.locator('a:has-text("Log In"), button:has-text("Log In"), a:has-text("Log in")')
                    signup_btn = page.locator('a:has-text("Sign Up")')

                    login_visible = False
                    try:
                        if await login_btn.count() > 0 and await login_btn.first.is_visible(timeout=3000):
                            login_visible = True
                    except Exception:
                        pass

                    signup_visible = False
                    try:
                        if await signup_btn.count() > 0 and await signup_btn.first.is_visible(timeout=3000):
                            signup_visible = True
                    except Exception:
                        pass

                    if login_visible or signup_visible:
                        logger.error("Login failed - login/signup buttons still visible on homepage")
                        await browser.close()
                        return None
                    else:
                        # No login buttons visible - likely logged in successfully
                        logger.info("Login appears successful - redirected to homepage without login buttons")

                # Extract ALL cookies (not just sgproof domain)
                cookies = await context.cookies()
                # Store full cookie format for Playwright reuse
                self._playwright_cookies = cookies
                for cookie in cookies:
                    cookies_dict[cookie["name"]] = cookie["value"]
                    logger.debug(f"Cookie: {cookie['name']} = {cookie['value'][:20]}... (domain: {cookie.get('domain', 'N/A')})")

                logger.info(f"Captured {len(cookies_dict)} cookies from SGWS")

                # Verify we're logged in by checking page content
                if cookies_dict:
                    logger.info("Login appears successful!")

            except Exception as e:
                logger.error(f"Playwright login error: {e}")
                await page.screenshot(path="/tmp/sgws_error.png")

            finally:
                await browser.close()

        return cookies_dict if cookies_dict else None

    async def get_categories(self) -> list[dict[str, Any]]:
        """Return predefined categories."""
        return self.CATEGORIES

    async def get_products(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[RawProduct]:
        """
        Fetch products from SGWS Proof using Playwright.

        SGWS is a JavaScript SPA, so we use Playwright to render
        the page and scrape product data from the DOM.

        Args:
            category: Category filter (e.g., "Spirits", "Wine")
            limit: Max products to fetch (None = all available)
            offset: Starting offset for pagination

        Returns:
            List of RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        # Use Playwright to scrape since SGWS is a JS SPA
        return await self._scrape_with_playwright(category, limit)

    async def _scrape_with_playwright(
        self,
        category: Optional[str],
        limit: Optional[int],
    ) -> list[RawProduct]:
        """
        Use Playwright to scrape products from SGWS (handles JS rendering).

        Args:
            category: Category filter
            limit: Max products to fetch

        Returns:
            List of RawProduct objects
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed")
            return []

        products: list[RawProduct] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            # Use stealth context factory for anti-detection
            context = await StealthContextFactory.create_context(browser)

            # Set cookies from authentication (use full Playwright cookie format)
            if self._playwright_cookies:
                await context.add_cookies(self._playwright_cookies)
                logger.info(f"Added {len(self._playwright_cookies)} cookies to Playwright context")

            page = await context.new_page()

            try:
                # Navigate to search page with category filter
                search_url = f"{self.base_url}/sgws/en/usd/search"
                if category:
                    search_url += f"?text=&f-category={category}"
                else:
                    search_url += "?text="

                logger.info(f"Navigating to: {search_url}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

                # Wait for SSO redirects to complete
                # SGWS uses Gigya SSO which does multiple redirects
                max_wait = 45  # seconds
                waited = 0
                last_url = ""
                stable_count = 0

                while waited < max_wait:
                    current_url = page.url

                    # Check if URL is stable (same for 3 checks = ~6 seconds)
                    if current_url == last_url:
                        stable_count += 1
                    else:
                        stable_count = 0
                        logger.info(f"Current URL (t={waited}s): {current_url}")

                    last_url = current_url

                    # If URL has been stable and we're on the main site, we're done
                    if stable_count >= 3 and "shop.sgproof.com" in current_url:
                        logger.info("SSO redirect complete, URL stable on main site")
                        break

                    # If on login page explicitly, session expired
                    if "/auth/login" in current_url or "/login" in current_url:
                        logger.warning("Redirected to login page - session expired")
                        await page.screenshot(path="/tmp/sgws_search.png")
                        return []

                    await asyncio.sleep(2)
                    waited += 2

                # Wait additional time for JS to render products
                await asyncio.sleep(5)

                # Handle age verification if it appears
                await self._handle_age_verification(page)

                # Handle holiday/promotional popup if it appears
                await self._handle_popup_dialogs(page)

                # CRITICAL: Verify we're actually logged in before scraping
                # First check for POSITIVE indicators (logged in)
                is_authenticated = False

                # Check for account number in header (e.g., "Acct: 102376")
                try:
                    acct_indicator = page.locator('text=/Acct:\\s*\\d+/')
                    if await acct_indicator.count() > 0:
                        logger.info("AUTHENTICATED - Account number visible in header")
                        is_authenticated = True
                except Exception:
                    pass

                # Check for "Add to Cart" buttons (only visible when logged in)
                try:
                    cart_buttons = page.locator('button:has-text("Add to Cart")')
                    if await cart_buttons.count() > 0:
                        logger.info("AUTHENTICATED - 'Add to Cart' buttons visible")
                        is_authenticated = True
                except Exception:
                    pass

                # Check for price elements with dollar amounts
                try:
                    prices = page.locator('text=/\\$\\d+\\.\\d{2}/')
                    price_count = await prices.count()
                    if price_count > 0:
                        logger.info(f"AUTHENTICATED - Found {price_count} price elements")
                        is_authenticated = True
                except Exception:
                    pass

                # If we found positive indicators, we're logged in - proceed
                if is_authenticated:
                    logger.info("Authentication verified via positive indicators")
                else:
                    # Only check negative indicators if no positive indicators found
                    is_not_authenticated = False

                    # Check for "Sign up to view product prices" text
                    try:
                        not_logged_in_check = page.locator('text="Sign up to view product prices"')
                        if await not_logged_in_check.count() > 0:
                            logger.error("NOT AUTHENTICATED - 'Sign up to view product prices' visible")
                            is_not_authenticated = True
                    except Exception:
                        pass

                    # Check for prominent Login/Sign Up buttons in header area
                    try:
                        # More specific: look in header/nav area only
                        header_login = page.locator('header a:has-text("Log In"), nav a:has-text("Log In")')
                        if await header_login.count() > 0 and await header_login.first.is_visible(timeout=2000):
                            logger.error("NOT AUTHENTICATED - Login button visible in header")
                            is_not_authenticated = True
                    except Exception:
                        pass

                if not is_authenticated and is_not_authenticated:
                    logger.error("Session expired or cookies invalid!")
                    logger.error("Clearing invalid cookies and aborting scrape")
                    await page.screenshot(path="/tmp/sgws_not_authenticated.png")

                    # Clear the invalid saved cookies
                    try:
                        from app.scrapers.utils.cookie_capture import COOKIES_DIR
                        cookie_file = COOKIES_DIR / "sgws_cookies.json"
                        if cookie_file.exists():
                            cookie_file.unlink()
                            logger.info("Deleted expired cookies file")
                    except Exception as e:
                        logger.debug(f"Could not delete cookie file: {e}")

                    # Mark as not authenticated
                    self.authenticated = False
                    self._playwright_cookies = []
                    self.session_cookies = {}

                    logger.error("Please run: python -m app.scrapers.utils.cookie_capture --distributor sgws")
                    return []

                logger.info("Authentication verified - proceeding with scrape")

                # Scroll down to trigger lazy loading
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)

                # Take screenshot for debugging
                await page.screenshot(path="/tmp/sgws_search.png")
                logger.info("Screenshot saved to /tmp/sgws_search.png")

                # Debug: save page HTML
                html_content = await page.content()
                with open("/tmp/sgws_search.html", "w") as f:
                    f.write(html_content)
                logger.info(f"Page HTML saved ({len(html_content)} chars)")

                # Handle cookie consent popup if present
                try:
                    accept_btn = page.locator('button:has-text("Accept All"), button:has-text("Accept"), [id*="accept"]')
                    if await accept_btn.count() > 0:
                        await accept_btn.first.click(timeout=5000)
                        logger.info("Clicked cookie accept button")
                        await asyncio.sleep(2)
                except Exception:
                    pass

                # SGWS uses React/MUI - use JavaScript to extract products with prices
                logger.info("Extracting products via JavaScript...")

                # Use JavaScript to find product cards and extract all data
                product_data = await page.evaluate('''
                    () => {
                        const products = [];
                        const seenSkus = new Set();

                        // Find all product links with href containing /p/ and frompage
                        const productLinks = document.querySelectorAll('a[href*="/p/"][href*="frompage"]');

                        for (const link of productLinks) {
                            try {
                                const href = link.getAttribute('href');
                                if (!href) continue;

                                // Extract SKU from URL
                                const skuMatch = href.match(/\\/p\\/(\\d+)/);
                                if (!skuMatch) continue;

                                const sku = skuMatch[1];
                                if (seenSkus.has(sku)) continue;
                                seenSkus.add(sku);

                                // Extract name from URL
                                const nameMatch = href.match(/\\/([^\\/]+)\\/p\\/\\d+/);
                                const name = nameMatch ? nameMatch[1].replace(/-/g, ' ').trim() : 'Product ' + sku;

                                // Find price - look for parent card and find price element
                                // Navigate up to find the product card container
                                let parent = link.parentElement;
                                let price = null;
                                let attempts = 0;

                                while (parent && attempts < 10) {
                                    // Look for price text in this container ($ followed by numbers)
                                    const priceElements = parent.querySelectorAll('*');
                                    for (const el of priceElements) {
                                        const text = el.textContent || '';
                                        // Match price pattern like $123.00 or $1,234.00
                                        const priceMatch = text.match(/\\$([\\d,]+\\.\\d{2})/);
                                        if (priceMatch && !text.includes('to') && text.trim().startsWith('$')) {
                                            // Clean and parse the price
                                            const priceStr = priceMatch[1].replace(/,/g, '');
                                            price = parseFloat(priceStr);
                                            break;
                                        }
                                    }
                                    if (price) break;
                                    parent = parent.parentElement;
                                    attempts++;
                                }

                                products.push({
                                    sku: sku,
                                    name: name,
                                    href: href,
                                    price: price
                                });
                            } catch (e) {
                                console.log('Error extracting product:', e);
                            }
                        }

                        return products;
                    }
                ''')

                logger.info(f"JavaScript extracted {len(product_data)} products")

                # Convert to RawProduct objects
                seen_skus: set[str] = set()
                for p_data in product_data:
                    sku = p_data.get('sku')
                    if not sku or sku in seen_skus:
                        continue
                    seen_skus.add(sku)

                    href = p_data.get('href', '')
                    products.append(RawProduct(
                        external_id=sku,
                        name=p_data.get('name', f'Product {sku}'),
                        category=category.lower() if category else None,
                        price=p_data.get('price'),
                        price_type="case",
                        url=f"{self.base_url}{href}" if href.startswith("/") else href,
                    ))

                    # Respect limit
                    if limit and len(products) >= limit:
                        break

                logger.info(f"Scraped {len(products)} products from Playwright")

            except Exception as e:
                logger.error(f"Playwright scraping error: {e}")
                import traceback
                logger.error(traceback.format_exc())

            finally:
                await browser.close()

        return products

    async def _scrape_html_search(
        self,
        category: Optional[str],
        page: int,
    ) -> list[RawProduct]:
        """
        Fallback: Scrape product data from HTML search results.

        Args:
            category: Category filter
            page: Page number

        Returns:
            List of RawProduct objects
        """
        products: list[RawProduct] = []

        # Build search URL - SGWS uses /sgws/en/usd/search format
        params = {"text": "", "currentPage": page}
        if category:
            params["f-category"] = category

        try:
            # Try the shop search URL
            response = await self._request(
                "GET",
                f"{self.base_url}/sgws/en/usd/search",
                params=params,
            )
            html = response.text
            logger.info(f"HTML search response length: {len(html)} chars")

            # Extract product data from HTML using various patterns

            # Pattern for product SKUs in URLs (e.g., /p/563699 or /p/SKU123)
            sku_pattern = r'/p/([A-Za-z0-9-]+)'
            skus = list(set(re.findall(sku_pattern, html)))  # Dedupe

            # Pattern for product names (various formats)
            name_patterns = [
                r'data-product-name="([^"]+)"',
                r'class="product-name[^"]*"[^>]*>([^<]+)<',
                r'title="([^"]+)"\s+class="[^"]*product',
                r'<h[23][^>]*class="[^"]*product[^"]*"[^>]*>([^<]+)<',
            ]
            names = []
            for pattern in name_patterns:
                found = re.findall(pattern, html)
                if found:
                    names.extend(found)
                    break

            # Pattern for prices
            price_pattern = r'\$([0-9,]+\.\d{2})'
            prices = re.findall(price_pattern, html)

            logger.info(f"Found {len(skus)} SKUs, {len(names)} names, {len(prices)} prices")

            # Create products from extracted data
            for i, sku in enumerate(skus[:50]):  # Limit to first 50
                name = names[i] if i < len(names) else f"Product {sku}"
                price = float(prices[i].replace(",", "")) if i < len(prices) else None

                products.append(RawProduct(
                    external_id=sku,
                    name=name,
                    category=category.lower() if category else None,
                    price=price,
                    price_type="case",
                    url=f"{self.base_url}/sgws/en/usd/product/p/{sku}",
                ))

            # If no products found, log sample of HTML for debugging
            if not products:
                logger.warning(f"No products parsed from HTML. First 500 chars: {html[:500]}")

        except Exception as e:
            logger.error(f"HTML scrape failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return products

    def _parse_product(
        self,
        data: dict[str, Any],
        category: Optional[str] = None,
    ) -> Optional[RawProduct]:
        """
        Parse SGWS API response into RawProduct.

        Args:
            data: Product data from API
            category: Category filter string

        Returns:
            RawProduct or None if parsing fails
        """
        try:
            # Extract SKU/external ID
            external_id = str(
                data.get("code")
                or data.get("sku")
                or data.get("productCode")
                or data.get("id")
                or ""
            )
            if not external_id:
                logger.warning(f"Product missing ID: {data.get('name')}")
                return None

            # Extract name
            name = (
                data.get("name")
                or data.get("productName")
                or data.get("displayName")
                or "Unknown"
            )

            # Extract brand (often in name or separate field)
            brand = data.get("brand") or data.get("manufacturer")
            if not brand and name:
                # Try to extract brand from name (usually first word(s))
                parts = name.split()
                if len(parts) > 1:
                    brand = parts[0]

            # Parse category
            parsed_category = None
            if category:
                parsed_category = category.lower()
            elif data.get("category"):
                parsed_category = data["category"].lower()

            # Parse subcategory
            parsed_subcategory = data.get("subcategory") or data.get("productType")

            # Extract volume (in ml)
            volume_ml = None
            size_str = data.get("size") or data.get("volume") or ""
            if size_str:
                # Parse sizes like "750ML", "1L", "1.75L"
                size_match = re.search(r'(\d+\.?\d*)\s*(ML|L|ml|l)', str(size_str), re.I)
                if size_match:
                    value = float(size_match.group(1))
                    unit = size_match.group(2).upper()
                    volume_ml = int(value * 1000 if unit == "L" else value)

            # Extract ABV
            abv = None
            abv_str = data.get("abv") or data.get("alcoholContent") or data.get("proof")
            if abv_str:
                try:
                    abv_val = float(re.sub(r'[^\d.]', '', str(abv_str)))
                    # If it looks like proof, convert to ABV
                    if abv_val > 100:
                        abv = abv_val / 2
                    else:
                        abv = abv_val
                except (ValueError, TypeError):
                    pass

            # Extract prices
            price = None
            price_type = "case"

            # Try case price first
            case_price = data.get("casePrice") or data.get("price", {}).get("value")
            if case_price:
                try:
                    price = float(str(case_price).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Unit price as fallback
            if not price:
                unit_price = data.get("unitPrice") or data.get("bottlePrice")
                if unit_price:
                    try:
                        price = float(str(unit_price).replace("$", "").replace(",", ""))
                        price_type = "bottle"
                    except (ValueError, TypeError):
                        pass

            # Inventory/stock status
            inventory = None
            in_stock = True
            stock_data = data.get("stock") or data.get("availability") or {}
            if isinstance(stock_data, dict):
                inventory = stock_data.get("stockLevel")
                in_stock = stock_data.get("inStock", True)
            elif data.get("inStock") is not None:
                in_stock = data.get("inStock")

            # Image URL
            image_url = None
            images = data.get("images") or []
            if images and isinstance(images, list):
                image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
            elif data.get("imageUrl"):
                image_url = data["imageUrl"]
            elif data.get("thumbnailUrl"):
                image_url = data["thumbnailUrl"]

            # Build product URL
            url_slug = data.get("url") or data.get("slug")
            if url_slug:
                url = f"{self.base_url}{url_slug}" if url_slug.startswith("/") else url_slug
            else:
                url = f"{self.base_url}/sgws/en/usd/product/p/{external_id}"

            # Description
            description = data.get("description") or data.get("summary")

            # UPC
            upc = data.get("upc") or data.get("ean") or data.get("barcode")

            return RawProduct(
                external_id=external_id,
                name=name,
                brand=brand,
                category=parsed_category,
                subcategory=parsed_subcategory,
                volume_ml=volume_ml,
                abv=abv,
                price=price,
                price_type=price_type,
                inventory=inventory,
                in_stock=in_stock,
                available_states=None,  # SGWS doesn't expose this in search
                image_url=image_url,
                description=description,
                upc=upc,
                url=url,
                raw_data=data,
            )

        except Exception as e:
            logger.error(f"Error parsing SGWS product: {e}")
            return None

    async def search_products(
        self,
        query: str,
        limit: int = 50,
    ) -> list[RawProduct]:
        """
        Search for products by name/keyword.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching RawProduct objects
        """
        if not self.authenticated:
            raise Exception("Not authenticated")

        params = {
            "text": query,
            "pageSize": min(limit, 100),
        }

        try:
            response = await self._request(
                "GET",
                f"{self.base_url}/sgws/en/usd/search/results",
                params=params,
            )
            data = response.json()

            products = []
            for p in data.get("products", [])[:limit]:
                product = self._parse_product(p)
                if product:
                    products.append(product)

            return products

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
