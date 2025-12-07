"""
ABVTrends - AI-Powered Content Extraction Service

Uses LLMs (GPT-4, Claude) to intelligently extract trend data from raw HTML/text
instead of relying on brittle CSS selectors.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTrend:
    """Structured output from AI extraction."""

    title: str
    summary: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    celebrity_affiliation: Optional[str] = None
    trend_reason: Optional[str] = None
    source_url: str = ""
    published_date: Optional[str] = None
    confidence_score: float = 1.0


class AIExtractor:
    """
    AI-powered content extraction service.

    Uses GPT-4 to interpret raw HTML and extract structured trend data.
    This approach is more robust than CSS selectors and adapts to site changes.
    """

    EXTRACTION_PROMPT = """You are an expert trend analyst for the alcohol beverage industry.

Your task is to analyze article/product page content and extract structured trend information.

Focus on:
- New product launches
- Celebrity/influencer partnerships
- Awards and accolades
- Regional or seasonal trends
- Retailer new arrivals
- Brand collaborations

Extract the following information and return ONLY valid JSON (no markdown, no explanation):

{
  "title": "Article or product title",
  "summary": "2-3 sentence summary of why this is trending",
  "product_name": "Full product name (null if not applicable)",
  "brand": "Brand name (e.g., 'Casa Dragones', 'Clase Azul')",
  "category": "spirits/wine/beer/rtd/sake (use null if unclear)",
  "subcategory": "tequila/whiskey/vodka/gin/rum/etc (null if unclear)",
  "celebrity_affiliation": "Celebrity/influencer name if applicable (null otherwise)",
  "trend_reason": "celebrity_launch/new_product/award/seasonal/regional/collaboration (null if unclear)",
  "published_date": "YYYY-MM-DD format if found, null otherwise",
  "confidence_score": 0.0-1.0 (how confident are you this is a real trend signal?)
}

If the content is not relevant to alcohol trends (e.g., recipes, general news), return:
{"title": null, "confidence_score": 0.0}

Content to analyze:
"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI extractor.

        Args:
            api_key: OpenAI API key (reads from env if not provided)
        """
        self.client = OpenAI(api_key=api_key)

    def clean_html(self, html: str) -> str:
        """
        Clean HTML to extract readable text while preserving structure.

        Args:
            html: Raw HTML content

        Returns:
            Cleaned text suitable for AI processing
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()

        # Get text with some structure
        text = soup.get_text(separator="\n", strip=True)

        # Remove excessive whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        # Limit to first 6000 chars to avoid token limits
        return text[:6000]

    async def extract_from_html(
        self, html: str, source_url: str
    ) -> Optional[ExtractedTrend]:
        """
        Extract trend data from raw HTML using AI.

        Args:
            html: Raw HTML content
            source_url: Source URL for reference

        Returns:
            ExtractedTrend object or None if extraction failed
        """
        try:
            # Clean HTML to text
            clean_text = self.clean_html(html)

            if len(clean_text) < 100:
                logger.warning(f"Content too short from {source_url}")
                return None

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert trend analyst for the alcohol beverage industry. Return only valid JSON, no markdown formatting.",
                    },
                    {
                        "role": "user",
                        "content": f"{self.EXTRACTION_PROMPT}\n\n{clean_text}",
                    },
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            # Parse response
            response_text = response.choices[0].message.content.strip()

            # Parse JSON
            data = json.loads(response_text)

            # Check if content was relevant
            if not data.get("title") or data.get("confidence_score", 0) < 0.3:
                logger.debug(f"Low confidence extraction from {source_url}")
                return None

            # Build ExtractedTrend object
            return ExtractedTrend(
                title=data["title"],
                summary=data["summary"],
                product_name=data.get("product_name"),
                brand=data.get("brand"),
                category=data.get("category"),
                celebrity_affiliation=data.get("celebrity_affiliation"),
                trend_reason=data.get("trend_reason"),
                source_url=source_url,
                published_date=data.get("published_date"),
                confidence_score=data.get("confidence_score", 1.0),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON from {source_url}: {e}")
            logger.debug(f"Response was: {response_text}")
            return None
        except Exception as e:
            logger.error(f"AI extraction failed for {source_url}: {e}")
            return None

    async def extract_from_text(
        self, text: str, source_url: str
    ) -> Optional[ExtractedTrend]:
        """
        Extract trend data from clean text using AI.

        Args:
            text: Clean text content
            source_url: Source URL for reference

        Returns:
            ExtractedTrend object or None if extraction failed
        """
        try:
            # Truncate if too long
            text = text[:6000]

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert trend analyst for the alcohol beverage industry. Return only valid JSON, no markdown formatting.",
                    },
                    {
                        "role": "user",
                        "content": f"{self.EXTRACTION_PROMPT}\n\n{text}",
                    },
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            # Parse response
            response_text = response.choices[0].message.content.strip()

            # Parse JSON
            data = json.loads(response_text)

            # Check relevance
            if not data.get("title") or data.get("confidence_score", 0) < 0.3:
                return None

            return ExtractedTrend(
                title=data["title"],
                summary=data["summary"],
                product_name=data.get("product_name"),
                brand=data.get("brand"),
                category=data.get("category"),
                celebrity_affiliation=data.get("celebrity_affiliation"),
                trend_reason=data.get("trend_reason"),
                source_url=source_url,
                published_date=data.get("published_date"),
                confidence_score=data.get("confidence_score", 1.0),
            )

        except Exception as e:
            logger.error(f"AI extraction failed for {source_url}: {e}")
            return None
