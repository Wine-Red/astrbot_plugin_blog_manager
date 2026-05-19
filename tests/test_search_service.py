from astrbot_plugin_blog_manager.services.search_service import (
    SearchService,
    parse_news_items_from_text,
)


class FakeAstrBotSearchContext:
    async def web_search(self, *, query, topic, time_range, max_results):
        return {
            "results": [
                {
                    "title": "AI chip demand grows",
                    "url": "https://example.com/ai-chip",
                    "snippet": "AI infrastructure spending continues to rise.",
                }
            ]
        }


def test_search_service_uses_astrbot_context_search():
    service = SearchService(enabled=True, context=FakeAstrBotSearchContext())

    import asyncio

    items = asyncio.run(service.search_news(["AI news today"], limit=5))

    assert len(items) == 1
    assert items[0].title == "AI chip demand grows"
    assert items[0].source == "example.com"


def test_parse_news_items_from_text_accepts_user_supplied_news():
    text = """
    1. AI影响就业：AI正在影响应届毕业生进入就业市场，技术行业发生变化。
    2. 汽车行业AI盈利困难：调查显示汽车制造商难以从AI中获利。
    3. AI安全漏洞：https://example.com/security Pwn2Own柏林大赛发现AI数据库零日漏洞。
    """

    items = parse_news_items_from_text(text)

    assert len(items) == 3
    assert items[0].source == "用户提供"
    assert items[2].url == "https://example.com/security"
