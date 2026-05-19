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


class EmptySearchService:
    async def search_news(self, queries, *, limit=5):
        return []


class FailingSearchService:
    async def search_news(self, queries, *, limit=5):
        raise RuntimeError("search unavailable")


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
    assert "## 今日数据源概览" in draft.body
    assert "## 新闻深度分析" in draft.body
    assert "## 综合判断" in draft.body
    assert "![AI 日报封面]" in draft.body
    assert "![OpenAI releases new agent tools]" in draft.body
    assert "[example.com](https://example.com/openai-agent)" in draft.body


def test_blog_service_generates_daily_draft_from_supplied_news_when_search_empty():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
            "article_format": "md",
        },
    )
    service.search_service = EmptySearchService()
    instructions = """
    1. AI影响就业：AI正在影响应届毕业生进入就业市场，技术行业发生变化。
    2. 汽车行业AI盈利困难：调查显示汽车制造商难以从AI中获利。
    3. AI安全漏洞：https://example.com/security Pwn2Own柏林大赛发现AI数据库零日漏洞。
    """

    draft = asyncio.run(
        service.generate_daily_draft(
            report_date=date(2026, 5, 19),
            extra_instructions=instructions,
        )
    )

    assert draft.slug == "ai-daily-2026-05-19"
    assert "AI影响就业" in draft.body
    assert "https://example.com/security" in draft.body


def test_blog_service_generates_daily_overview_when_no_news_available():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
            "article_format": "md",
        },
    )
    service.search_service = EmptySearchService()

    draft = asyncio.run(service.generate_daily_draft(report_date=date(2026, 5, 19)))

    assert draft.slug == "ai-daily-2026-05-19"
    assert draft.title.startswith("AI 日报-日期：2026-05-19")
    assert "暂未获取到足够新闻源" in draft.body
    assert draft.frontmatter["image"].startswith("https://image.pollinations.ai/prompt/")


def test_blog_service_generates_daily_overview_when_search_fails():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
            "article_format": "md",
        },
    )
    service.search_service = FailingSearchService()

    draft = asyncio.run(service.generate_daily_draft(report_date=date(2026, 5, 19)))

    assert draft.slug == "ai-daily-2026-05-19"
    assert "暂未获取到足够新闻源" in draft.body
