import asyncio
from datetime import date

from astrbot_plugin_blog_manager.models import NewsItem
from astrbot_plugin_blog_manager.services.blog_service import BlogService


class FakeSearchService:
    async def search_news(self, queries, *, limit=5):
        return [
            NewsItem(
                title="OpenAI releases new agent tools",
                summary="OpenAI announced new agent tooling for enterprise workflows.",
                url="https://example.com/openai-agent",
                source="example.com",
            ),
            NewsItem(
                title="LLM benchmark improves",
                summary="A new LLM benchmark shows stronger reasoning results.",
                url="https://example.com/llm-benchmark",
                source="example.com",
            ),
            NewsItem(
                title="AI chip demand grows",
                summary="AI infrastructure spending continues to rise.",
                url="https://example.com/ai-chip",
                source="example.com",
            ),
        ]


def test_blog_service_generates_daily_draft_with_firefly_frontmatter():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
            "article_format": "md",
        },
    )
    service.search_service = FakeSearchService()

    draft = asyncio.run(service.generate_daily_draft(report_date=date(2026, 5, 19)))

    assert draft.slug == "ai-daily-2026-05-19"
    assert draft.slug.isascii()
    assert draft.title.startswith("AI 日报-日期：2026-05-19")
    assert draft.frontmatter["category"] == "AI资讯"
    assert draft.frontmatter["tags"][:3] == ["AI", "日报", "人工智能"]
    assert draft.frontmatter["image"].startswith("https://image.pollinations.ai/prompt/")
    assert "## 开篇语" in draft.body
    assert "## 新闻列表" in draft.body
    assert "[example.com](https://example.com/openai-agent)" in draft.body
