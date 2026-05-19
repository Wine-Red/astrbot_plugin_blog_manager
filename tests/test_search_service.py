from astrbot_plugin_blog_manager.services.search_service import parse_duckduckgo_html


def test_parse_duckduckgo_html_extracts_news_items():
    html = """
    <div class="result">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fai-news">OpenAI launches demo</a>
      <a class="result__snippet">A short summary about a new AI product.</a>
    </div>
    """

    items = parse_duckduckgo_html(html)

    assert len(items) == 1
    assert items[0].title == "OpenAI launches demo"
    assert items[0].summary == "A short summary about a new AI product."
    assert items[0].url == "https://example.com/ai-news"
    assert items[0].source == "example.com"
