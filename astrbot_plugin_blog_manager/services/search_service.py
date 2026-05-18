"""Search integration placeholder."""

from __future__ import annotations

from ..exceptions import SearchDisabledError


class SearchService:
    """A placeholder search service for future web-search powered generation."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    async def search(self, query: str) -> list[str]:
        if not self.enabled:
            raise SearchDisabledError("当前未启用搜索增强能力。")
        return [f"搜索占位结果: {query}"]
