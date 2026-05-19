from astrbot_plugin_blog_manager.models import NewsItem
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


def test_search_service_falls_back_to_duckduckgo_when_context_empty():
    class FallbackService(SearchService):
        async def _search_with_context(self, query):
            return []

        async def _search_with_duckduckgo(self, query):
            return [
                NewsItem(
                    title="OpenAI releases agent tools",
                    summary="OpenAI announced new agent tooling.",
                    url="https://example.com/openai-agent",
                    source="example.com",
                )
            ]

    service = FallbackService(enabled=True)

    import asyncio

    items = asyncio.run(service.search_news(["AI news today"], limit=5))

    assert len(items) == 1
    assert items[0].title == "OpenAI releases agent tools"


def test_search_service_parses_duckduckgo_html_results():
    service = SearchService(enabled=True)
    html = """
    <div class="result">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fopenai-agent">OpenAI releases agent tools</a>
      <a class="result__snippet">OpenAI announced new agent tooling for enterprise workflows.</a>
    </div>
    <div class="result">
      <a rel="nofollow" class="result__a" href="https://example.org/llm">LLM benchmark improves</a>
      <div class="result__snippet">A new benchmark reports stronger reasoning results.</div>
    </div>
    """

    items = service._parse_duckduckgo_html(html)

    assert len(items) == 2
    assert items[0].title == "OpenAI releases agent tools"
    assert items[0].url == "https://example.com/openai-agent"
    assert items[0].source == "example.com"
    assert items[1].summary == "A new benchmark reports stronger reasoning results."


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
