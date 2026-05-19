"""Search integration for news-powered article generation."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from ..exceptions import SearchDisabledError
from ..models import NewsItem


DEFAULT_AI_NEWS_QUERIES = [
    "AI news today",
    "人工智能 最新进展",
    "LLM breakthroughs",
]


class SearchService:
    """Collect news items from AstrBot search hooks or DuckDuckGo HTML."""

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
            if not query_items:
                query_items = await self._search_duckduckgo(query)
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

        for method_name in ("web_search", "search_web", "search"):
            method = getattr(self.context, method_name, None)
            if not callable(method):
                continue
            try:
                raw_results = await method(query)
            except Exception:
                continue
            parsed = self._parse_context_results(raw_results)
            if parsed:
                return parsed
        return []

    def _parse_context_results(self, raw_results: Any) -> list[NewsItem]:
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

    async def _search_duckduckgo(self, query: str) -> list[NewsItem]:
        try:
            import httpx
        except ImportError:
            return []

        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": "astrbot-plugin-blog-manager/1.0"}
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
                response = await client.get(url)
        except httpx.HTTPError:
            return []
        if response.status_code >= 400:
            return []
        return parse_duckduckgo_html(response.text)

    def _source_from_url(self, url: str) -> str:
        hostname = urlparse(url).netloc.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname


def parse_duckduckgo_html(document: str) -> list[NewsItem]:
    """Parse DuckDuckGo HTML results without third-party parser dependencies."""

    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>'
        r".*?"
        r'(?:<a[^>]+class="result__snippet"[^>]*>(?P<snippet_a>.*?)</a>|'
        r'<div[^>]+class="result__snippet"[^>]*>(?P<snippet_div>.*?)</div>)',
        re.IGNORECASE | re.DOTALL,
    )
    items: list[NewsItem] = []
    for match in pattern.finditer(document):
        raw_url = html.unescape(match.group("href"))
        title = _strip_html(match.group("title"))
        summary = _strip_html(match.group("snippet_a") or match.group("snippet_div") or "")
        url = _normalize_duckduckgo_url(raw_url)
        if not title or not url:
            continue
        items.append(
            NewsItem(
                title=title,
                summary=summary or title,
                url=url,
                source=_source_from_url(url),
            )
        )
    return items


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).strip()


def _normalize_duckduckgo_url(value: str) -> str:
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return value


def _source_from_url(url: str) -> str:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname
