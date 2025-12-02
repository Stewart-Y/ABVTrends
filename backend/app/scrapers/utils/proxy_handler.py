"""
ABVTrends - Proxy Handler

Manages proxy rotation for scrapers to avoid IP blocking.
Supports multiple proxy providers and automatic failover.
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Proxy:
    """Represents a proxy server."""

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

    # Tracking
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    is_blocked: bool = False
    blocked_until: Optional[datetime] = None

    @property
    def url(self) -> str:
        """Get proxy URL string."""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def record_success(self) -> None:
        """Record a successful request."""
        self.success_count += 1
        self.last_used = datetime.utcnow()
        self.last_error = None

    def record_failure(self, error: str) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_used = datetime.utcnow()
        self.last_error = error

        # Block proxy if too many failures
        if self.failure_count >= 5 and self.success_rate < 0.5:
            self.is_blocked = True
            self.blocked_until = datetime.utcnow() + timedelta(hours=1)
            logger.warning(f"Proxy {self.host}:{self.port} blocked due to failures")

    def is_available(self) -> bool:
        """Check if proxy is available for use."""
        if not self.is_blocked:
            return True

        # Check if block period has expired
        if self.blocked_until and datetime.utcnow() > self.blocked_until:
            self.is_blocked = False
            self.blocked_until = None
            self.failure_count = 0  # Reset failure count
            return True

        return False


class ProxyHandler:
    """
    Manages a pool of proxy servers with rotation and health tracking.

    Features:
    - Weighted random selection based on success rate
    - Automatic blocking of failing proxies
    - Support for multiple proxy providers
    - Fallback to direct connection if all proxies fail
    """

    def __init__(self, proxies: Optional[list[Proxy]] = None):
        """
        Initialize proxy handler.

        Args:
            proxies: List of Proxy objects. If None, uses direct connection.
        """
        self.proxies: list[Proxy] = proxies or []
        self._current_index: int = 0

    def add_proxy(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        protocol: str = "http",
    ) -> None:
        """Add a proxy to the pool."""
        proxy = Proxy(
            host=host,
            port=port,
            username=username,
            password=password,
            protocol=protocol,
        )
        self.proxies.append(proxy)
        logger.info(f"Added proxy {host}:{port} to pool")

    def add_proxy_from_url(self, url: str) -> None:
        """
        Add a proxy from URL string.

        Supports formats:
        - http://host:port
        - http://user:pass@host:port
        - socks5://host:port
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        self.add_proxy(
            host=parsed.hostname or "",
            port=parsed.port or 80,
            username=parsed.username,
            password=parsed.password,
            protocol=parsed.scheme or "http",
        )

    def get_available_proxies(self) -> list[Proxy]:
        """Get list of available (non-blocked) proxies."""
        return [p for p in self.proxies if p.is_available()]

    def get_proxy(self) -> Optional[Proxy]:
        """
        Get a proxy using weighted random selection.

        Proxies with higher success rates are more likely to be selected.

        Returns:
            Proxy object or None if no proxies available
        """
        available = self.get_available_proxies()

        if not available:
            logger.warning("No proxies available, using direct connection")
            return None

        # Weighted random selection based on success rate
        weights = [p.success_rate + 0.1 for p in available]  # +0.1 to give new proxies a chance
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        return random.choices(available, weights=weights, k=1)[0]

    def get_proxy_round_robin(self) -> Optional[Proxy]:
        """
        Get next proxy using round-robin selection.

        Returns:
            Proxy object or None if no proxies available
        """
        available = self.get_available_proxies()

        if not available:
            return None

        proxy = available[self._current_index % len(available)]
        self._current_index += 1
        return proxy

    def get_httpx_proxy_config(self, proxy: Optional[Proxy] = None) -> Optional[str]:
        """
        Get proxy configuration for httpx client.

        Args:
            proxy: Specific proxy to use, or None to select automatically

        Returns:
            Proxy URL string or None for direct connection
        """
        if proxy is None:
            proxy = self.get_proxy()

        if proxy is None:
            return None

        return proxy.url

    def report_success(self, proxy: Proxy) -> None:
        """Report successful request through proxy."""
        proxy.record_success()

    def report_failure(self, proxy: Proxy, error: str) -> None:
        """Report failed request through proxy."""
        proxy.record_failure(error)

    def get_stats(self) -> dict:
        """Get statistics about proxy pool."""
        available = self.get_available_proxies()
        blocked = [p for p in self.proxies if p.is_blocked]

        return {
            "total_proxies": len(self.proxies),
            "available_proxies": len(available),
            "blocked_proxies": len(blocked),
            "proxy_details": [
                {
                    "host": p.host,
                    "port": p.port,
                    "success_rate": p.success_rate,
                    "is_blocked": p.is_blocked,
                    "last_error": p.last_error,
                }
                for p in self.proxies
            ],
        }

    def clear_blocked(self) -> int:
        """
        Clear all blocked proxies.

        Returns:
            Number of proxies unblocked
        """
        count = 0
        for proxy in self.proxies:
            if proxy.is_blocked:
                proxy.is_blocked = False
                proxy.blocked_until = None
                proxy.failure_count = 0
                count += 1

        logger.info(f"Cleared {count} blocked proxies")
        return count


class ProxyRotatingClient:
    """
    HTTPX client wrapper with automatic proxy rotation.

    Usage:
        handler = ProxyHandler()
        handler.add_proxy("proxy1.example.com", 8080)

        async with ProxyRotatingClient(handler) as client:
            response = await client.get("https://example.com")
    """

    def __init__(self, proxy_handler: ProxyHandler):
        self.proxy_handler = proxy_handler
        self._client: Optional[httpx.AsyncClient] = None
        self._current_proxy: Optional[Proxy] = None

    async def _get_client(self, proxy: Optional[Proxy] = None) -> httpx.AsyncClient:
        """Get or create HTTP client with proxy."""
        proxy_url = self.proxy_handler.get_httpx_proxy_config(proxy)

        if self._client is not None:
            await self._client.aclose()

        self._current_proxy = proxy
        self._client = httpx.AsyncClient(
            proxy=proxy_url,
            timeout=httpx.Timeout(settings.scraper_timeout_seconds),
            follow_redirects=True,
        )
        return self._client

    async def get(
        self,
        url: str,
        headers: Optional[dict] = None,
        retry_on_failure: bool = True,
    ) -> httpx.Response:
        """
        Make GET request with automatic proxy rotation on failure.

        Args:
            url: URL to fetch
            headers: Optional request headers
            retry_on_failure: Whether to retry with different proxy on failure

        Returns:
            httpx.Response object
        """
        proxy = self.proxy_handler.get_proxy()
        client = await self._get_client(proxy)

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            if proxy:
                self.proxy_handler.report_success(proxy)

            return response

        except Exception as e:
            if proxy:
                self.proxy_handler.report_failure(proxy, str(e))

            if retry_on_failure:
                # Try with a different proxy
                new_proxy = self.proxy_handler.get_proxy()
                if new_proxy and new_proxy != proxy:
                    logger.info(f"Retrying with different proxy: {new_proxy.host}")
                    client = await self._get_client(new_proxy)
                    return await client.get(url, headers=headers)

            raise

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Default proxy handler (no proxies - direct connection)
default_proxy_handler = ProxyHandler()
