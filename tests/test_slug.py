from astrbot_plugin_blog_manager.utils.slug import slugify


def test_slugify_normalizes_text():
    assert slugify("Hello Astro Blog") == "hello-astro-blog"


def test_slugify_replaces_cjk_text_with_stable_ascii_fallback():
    slug = slugify("中文标题")

    assert slug.startswith("untitled-post-")
    assert slug.isascii()


def test_slugify_handles_mixed_text_and_spacing():
    assert slugify("示例文章：Welcome to 我的博客") == "welcome-to"
