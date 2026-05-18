from astrbot_plugin_blog_manager.utils.slug import slugify


def test_slugify_normalizes_text():
    assert slugify("Hello Astro Blog") == "hello-astro-blog"


def test_slugify_preserves_cjk_text():
    assert slugify("中文标题") == "中文标题"


def test_slugify_handles_mixed_text_and_spacing():
    assert slugify("示例文章：欢迎来到我的博客") == "示例文章-欢迎来到我的博客"
