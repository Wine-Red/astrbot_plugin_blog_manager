"""Search integration for news-powered article generation."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote_plus, urlparse

from ..exceptions import SearchDisabledError
from ..models import NewsItem


DEFAULT_AI_NEWS_QUERIES = [
    "AI news today",
    "人工智能 最新进展",
    "LLM breakthroughs",
]


class SearchService:
    """Collect news items from AstrBot built-in search hooks."""

    def __init__(self, enabled: bool = True, context: Any | None = None):
        self.enabled = enabled
        self.context = context

    async def search(self, query: str) -> list[str]:
        """Backward-compatible plain search API."""

        items = await self.search_news([query], limit=5)
        return [f"{item.title} - {item.url}" for item in items]

    async def search_news(
        self,
        queries: list[str] | None = None,
        *,
        limit: int = 5,
    ) -> list[NewsItem]:
        if not self.enabled:
            raise SearchDisabledError("当前未启用搜索增强能力。")

        queries = queries or DEFAULT_AI_NEWS_QUERIES
        items: list[NewsItem] = []
        seen_urls: set[str] = set()
        for query in queries:
            query_items = await self._search_with_context(query)
            for item in query_items:
                url = item.url.strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                items.append(item)
                if len(items) >= limit:
                    return items
        return items

    async def _search_with_context(self, query: str) -> list[NewsItem]:
        if self.context is None:
            return []

        for method_name in (
            "web_search",
            "search_web",
            "search",
            "search_tool",
            "builtin_search",
        ):
            method = getattr(self.context, method_name, None)
            if not callable(method):
                continue
            call_attempts = (
                lambda: method(query),
                lambda: method(query=query, topic="news", time_range="day", max_results=10),
                lambda: method(query=query, max_results=10),
            )
            for build_call in call_attempts:
                try:
                    raw_results = await build_call()
                except Exception:
                    continue
                parsed = self._parse_context_results(raw_results)
                if parsed:
                    return parsed
        return []

    def _parse_context_results(self, raw_results: Any) -> list[NewsItem]:
        if isinstance(raw_results, dict):
            raw_results = raw_results.get("results") or raw_results.get("items") or []
        if not isinstance(raw_results, list):
            return []

        items: list[NewsItem] = []
        for raw in raw_results:
            if isinstance(raw, str):
                text = raw.strip()
                if text:
                    items.append(NewsItem(title=text, summary=text, url="", source="AstrBot"))
                continue
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or raw.get("name") or "").strip()
            summary = str(
                raw.get("summary") or raw.get("snippet") or raw.get("content") or ""
            ).strip()
            url = str(raw.get("url") or raw.get("link") or "").strip()
            source = str(raw.get("source") or raw.get("site") or "").strip()
            if title and url:
                items.append(
                    NewsItem(
                        title=title,
                        summary=summary or title,
                        url=url,
                        source=source or self._source_from_url(url),
                    )
                )
        return items

    def _source_from_url(self, url: str) -> str:
        hostname = urlparse(url).netloc.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname


def parse_news_items_from_text(text: str) -> list[NewsItem]:
    """Extract user-supplied news snippets from plain text instructions."""

    chunks = re.split(r"\n\s*(?:\d+[\).、]|[-*])\s+", "\n" + text.strip())
    items: list[NewsItem] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        url_match = re.search(r"https?://[^\s)）]+", chunk)
        url = url_match.group(0).rstrip(".,;，。；") if url_match else ""
        title = chunk.splitlines()[0].strip(" -：:")
        title = re.sub(r"https?://\S+", "", title).strip(" -：:")
        summary = re.sub(r"https?://\S+", "", chunk).strip()
        if len(title) > 120:
            title = title[:120].rstrip() + "..."
        if title and (url or len(summary) >= 12):
            items.append(
                NewsItem(
                    title=title,
                    summary=summary or title,
                    url=url or f"https://www.google.com/search?q={quote_plus(title)}",
                    source=_source_from_url(url) if url else "用户提供",
                )
            )
    return items


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).strip()


def _source_from_url(url: str) -> str:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname
