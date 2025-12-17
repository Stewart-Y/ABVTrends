"""
ABVTrends - Discord Notifier

Sends scraper alerts and summaries to Discord via webhooks.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """
    Send notifications to Discord channels via webhooks.

    Notification types:
    - Errors: Auth failures, scrape failures, rate limiting
    - Summaries: Daily scraping stats
    - Alerts: Budget exhausted, consecutive failures
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.discord_webhook_url
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            logger.warning("Discord notifications disabled - no webhook URL configured")

    async def send(
        self,
        title: str,
        description: str,
        color: int = 0x5865F2,  # Discord blurple
        fields: Optional[list[dict]] = None,
        footer: Optional[str] = None,
    ) -> bool:
        """
        Send an embed message to Discord.

        Args:
            title: Message title
            description: Main message content
            color: Embed color (hex)
            fields: List of {name, value, inline} dicts
            footer: Footer text

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if fields:
            embed["fields"] = fields

        if footer:
            embed["footer"] = {"text": footer}

        payload = {"embeds": [embed]}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                return True

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    # ==========================================================================
    # Pre-built notification types
    # ==========================================================================

    async def scraper_error(
        self,
        distributor: str,
        error: str,
        context: Optional[dict] = None,
    ) -> bool:
        """Send error notification for a scraper failure."""
        fields = [
            {"name": "Distributor", "value": distributor.upper(), "inline": True},
            {"name": "Time", "value": datetime.utcnow().strftime("%H:%M UTC"), "inline": True},
        ]

        if context:
            for key, value in context.items():
                fields.append({"name": key, "value": str(value), "inline": True})

        return await self.send(
            title="🚨 Scraper Error",
            description=f"```\n{error[:500]}\n```",
            color=0xED4245,  # Red
            fields=fields,
            footer="Check logs for full details",
        )

    async def auth_failed(self, distributor: str, reason: str) -> bool:
        """Send notification for authentication failure."""
        return await self.send(
            title="🔐 Authentication Failed",
            description=f"Failed to authenticate with **{distributor.upper()}**",
            color=0xFEE75C,  # Yellow
            fields=[
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "Action", "value": "Check credentials in .env", "inline": False},
            ],
        )

    async def rate_limited(self, distributor: str, wait_seconds: int) -> bool:
        """Send notification for rate limiting."""
        return await self.send(
            title="⏳ Rate Limited",
            description=f"**{distributor.upper()}** rate limited the scraper",
            color=0xFEE75C,  # Yellow
            fields=[
                {"name": "Wait Time", "value": f"{wait_seconds}s", "inline": True},
            ],
        )

    async def daily_summary(self, stats: dict[str, dict]) -> bool:
        """Send daily scraping summary."""
        total_scraped = sum(s.get("items_scraped", 0) for s in stats.values())
        total_errors = sum(1 for s in stats.values() if s.get("errors", 0) > 0)

        # Build distributor breakdown
        breakdown = []
        for slug, data in sorted(stats.items()):
            scraped = data.get("items_scraped", 0)
            limit = data.get("daily_limit", 150)
            pct = (scraped / limit * 100) if limit > 0 else 0
            status = "✅" if scraped > 0 else "⚠️"
            breakdown.append(f"{status} **{slug}**: {scraped}/{limit} ({pct:.0f}%)")

        return await self.send(
            title="📊 Daily Scraping Summary",
            description="\n".join(breakdown),
            color=0x57F287 if total_errors == 0 else 0xFEE75C,  # Green or Yellow
            fields=[
                {"name": "Total Products", "value": str(total_scraped), "inline": True},
                {"name": "Distributors", "value": str(len(stats)), "inline": True},
                {"name": "Errors", "value": str(total_errors), "inline": True},
            ],
            footer=f"ABVTrends Stealth Scraper • {datetime.utcnow().strftime('%Y-%m-%d')}",
        )

    async def session_complete(
        self,
        distributor: str,
        products: int,
        total_today: int,
        daily_limit: int,
    ) -> bool:
        """Send notification when a scraping session completes."""
        pct = (total_today / daily_limit * 100) if daily_limit > 0 else 0

        return await self.send(
            title="✅ Scrape Complete",
            description=f"**{distributor.upper()}** session finished",
            color=0x57F287,  # Green
            fields=[
                {"name": "Products", "value": str(products), "inline": True},
                {"name": "Today's Total", "value": f"{total_today}/{daily_limit}", "inline": True},
                {"name": "Progress", "value": f"{pct:.0f}%", "inline": True},
            ],
        )

    async def budget_exhausted(self, distributor: str) -> bool:
        """Send notification when daily budget is exhausted."""
        return await self.send(
            title="📈 Daily Budget Reached",
            description=f"**{distributor.upper()}** has hit its daily scraping limit",
            color=0x5865F2,  # Blurple (informational)
            fields=[
                {"name": "Status", "value": "Will resume tomorrow", "inline": False},
            ],
        )

    async def scraper_started(self, distributors: list[str]) -> bool:
        """Send notification when stealth session starts."""
        return await self.send(
            title="🚀 Stealth Session Started",
            description=f"Scraping: **{', '.join(d.upper() for d in distributors)}**",
            color=0x5865F2,  # Blurple
        )


# Singleton instance
_notifier: Optional[DiscordNotifier] = None


def get_discord_notifier() -> DiscordNotifier:
    """Get or create the Discord notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = DiscordNotifier()
    return _notifier


# Convenience functions
async def notify_error(distributor: str, error: str, **context) -> bool:
    """Send error notification."""
    return await get_discord_notifier().scraper_error(distributor, error, context)


async def notify_auth_failed(distributor: str, reason: str) -> bool:
    """Send auth failure notification."""
    return await get_discord_notifier().auth_failed(distributor, reason)


async def notify_daily_summary(stats: dict) -> bool:
    """Send daily summary notification."""
    return await get_discord_notifier().daily_summary(stats)


async def notify_session_complete(
    distributor: str,
    products: int,
    total_today: int,
    daily_limit: int,
) -> bool:
    """Send session complete notification."""
    return await get_discord_notifier().session_complete(
        distributor, products, total_today, daily_limit
    )
