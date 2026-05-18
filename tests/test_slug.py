from astrbot_plugin_blog_manager.utils.slug import slugify


def test_slugify_normalizes_text():
    assert slugify("Hello Astro Blog") == "hello-astro-blog"


def test_slugify_ignores_non_ascii_and_uses_default():
    assert slugify("中文标题") == "untitled-post"
