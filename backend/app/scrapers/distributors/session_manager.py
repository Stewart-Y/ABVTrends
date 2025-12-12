"""
ABVTrends - Session Manager

Manages authentication sessions for distributor scrapers.
Supports both local (.env) and AWS Secrets Manager credential storage.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages authentication sessions for distributor scrapers.

    - Stores sessions in AWS Secrets Manager or locally
    - Tracks session expiration
    - Auto-refreshes via Playwright when expired
    """

    def __init__(self, use_aws: bool = False):
        """
        Initialize session manager.

        Args:
            use_aws: If True, use AWS Secrets Manager. Otherwise use .env
        """
        self.use_aws = use_aws
        self.secrets_client = None
        self._local_cache: dict[str, dict[str, Any]] = {}

        if use_aws:
            try:
                import boto3
                self.secrets_client = boto3.client("secretsmanager")
            except ImportError:
                logger.warning("boto3 not installed, falling back to local")
                self.use_aws = False

    async def get_session(self, distributor: str) -> dict[str, Any]:
        """
        Get valid session credentials for a distributor.
        Refreshes if expired.

        Args:
            distributor: Distributor name (e.g., "libdib")

        Returns:
            Dict with credentials and session tokens
        """
        # Get current session
        session_data = await self._get_credentials(distributor)

        if not session_data:
            raise Exception(f"No credentials found for {distributor}")

        # Check if session is expired
        expires_at = session_data.get("expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
                if datetime.utcnow() > expires_dt:
                    # Session expired, refresh
                    logger.info(f"Session expired for {distributor}, refreshing...")
                    session_data = await self._refresh_session(
                        distributor, session_data
                    )
            except ValueError:
                # Invalid date format, proceed with existing session
                pass

        return session_data

    async def _get_credentials(
        self, distributor: str
    ) -> Optional[dict[str, Any]]:
        """
        Get credentials from AWS Secrets Manager or environment.

        Args:
            distributor: Distributor name

        Returns:
            Dict with credentials or None
        """
        if self.use_aws and self.secrets_client:
            return await self._get_from_aws(distributor)
        else:
            return self._get_from_env(distributor)

    async def _get_from_aws(
        self, distributor: str
    ) -> Optional[dict[str, Any]]:
        """Get credentials from AWS Secrets Manager."""
        secret_name = f"abvtrends/{distributor}"
        try:
            response = self.secrets_client.get_secret_value(
                SecretId=secret_name
            )
            return json.loads(response["SecretString"])
        except Exception as e:
            logger.error(f"Failed to get secret {secret_name}: {e}")
            return None

    def _get_from_env(self, distributor: str) -> Optional[dict[str, Any]]:
        """
        Get credentials from environment variables.

        For LibDib, looks for:
        - LIBDIB_EMAIL
        - LIBDIB_PASSWORD
        - LIBDIB_ENTITY_SLUG
        - LIBDIB_SESSION_ID
        - LIBDIB_CSRF_TOKEN
        """
        prefix = distributor.upper()

        # Check if we have the basic credentials
        email = os.getenv(f"{prefix}_EMAIL")
        password = os.getenv(f"{prefix}_PASSWORD")

        if not email or not password:
            return None

        return {
            "email": email,
            "password": password,
            "entity_slug": os.getenv(f"{prefix}_ENTITY_SLUG", ""),
            "session_id": os.getenv(f"{prefix}_SESSION_ID"),
            "csrf_token": os.getenv(f"{prefix}_CSRF_TOKEN"),
            "expires_at": None,  # No expiration for env-based sessions
        }

    async def _save_credentials(
        self, distributor: str, data: dict[str, Any]
    ) -> None:
        """Save updated credentials."""
        if self.use_aws and self.secrets_client:
            secret_name = f"abvtrends/{distributor}"
            try:
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(data),
                )
            except Exception as e:
                logger.error(f"Failed to save secret {secret_name}: {e}")
        else:
            # For local, update the cache only
            self._local_cache[distributor] = data

    async def _refresh_session(
        self, distributor: str, credentials: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Refresh session using Playwright.
        Logs in fresh and captures new cookies.

        Args:
            distributor: Distributor name
            credentials: Current credentials

        Returns:
            Updated credentials with new session tokens
        """
        refresh_method = getattr(self, f"_refresh_{distributor}", None)
        if refresh_method:
            return await refresh_method(credentials)
        else:
            logger.warning(f"No refresh method for {distributor}")
            return credentials

    async def _refresh_libdib(
        self, credentials: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Refresh LibDib session via Playwright.

        Args:
            credentials: Current credentials with email/password

        Returns:
            Updated credentials with new session tokens
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed")
            return credentials

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Navigate to login
                await page.goto("https://app.libdib.com/login")

                # Wait for form to load
                await page.wait_for_selector('input[name="email"]', timeout=10000)

                # Fill login form
                await page.fill('input[name="email"]', credentials["email"])
                await page.fill('input[name="password"]', credentials["password"])

                # Click submit
                await page.click('button[type="submit"]')

                # Wait for redirect after login
                await page.wait_for_url("**/home/**", timeout=30000)

                # Extract cookies
                cookies = await context.cookies()
                session_id = next(
                    (c["value"] for c in cookies if c["name"] == "sessionid"),
                    None,
                )
                csrf_token = next(
                    (c["value"] for c in cookies if c["name"] == "csrftoken"),
                    None,
                )

                if not session_id or not csrf_token:
                    logger.error("Failed to extract session cookies")
                    return credentials

                # Update credentials
                new_creds = {
                    **credentials,
                    "session_id": session_id,
                    "csrf_token": csrf_token,
                    "expires_at": (
                        datetime.utcnow() + timedelta(hours=12)
                    ).isoformat(),
                }

                # Save to storage
                await self._save_credentials("libdib", new_creds)

                logger.info("LibDib session refreshed successfully")
                return new_creds

            except Exception as e:
                logger.error(f"Failed to refresh LibDib session: {e}")
                return credentials

            finally:
                await browser.close()
