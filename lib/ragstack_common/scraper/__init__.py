"""
Web scraping module for RAGStack-Lambda.

This module provides URL discovery, content fetching, HTML-to-Markdown extraction,
and content deduplication for ingesting web documentation into the Bedrock Knowledge Base.

Architecture:
- Discovery: Recursive URL discovery via SQS with scope enforcement
- Fetcher: HTTP-first with Playwright fallback for SPAs
- Extractor: HTML sanitization and Markdown conversion
- Dedup: Content-hash based deduplication across scrape jobs
"""

from ragstack_common.scraper.models import (
    ScrapeConfig,
    ScrapeJob,
    ScrapePage,
    ScrapeScope,
    ScrapeStatus,
    UrlStatus,
)

__all__ = [
    "ScrapeConfig",
    "ScrapeJob",
    "ScrapePage",
    "ScrapeScope",
    "ScrapeStatus",
    "UrlStatus",
]
