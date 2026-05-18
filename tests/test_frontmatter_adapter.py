from astrbot_plugin_blog_manager.adapters.frontmatter_adapter import build_frontmatter
from astrbot_plugin_blog_manager.models import AstroArticleDraft, BlogGenerateRequest


def test_build_frontmatter_merges_defaults_and_runtime_fields():
    config = {
        "default_frontmatter_template": {"draft": False, "layout": "post"},
        "required_frontmatter_fields": ["title", "description", "pubDate", "slug"],
    }
    request = BlogGenerateRequest(topic="Astro 发布")
    draft = AstroArticleDraft(
        title="Astro 发布",
        description="Astro 发布说明",
        body="# Demo",
        slug="astro-publish",
        tags=["astro", "blog"],
    )

    frontmatter = build_frontmatter(config, request, draft)

    assert frontmatter["title"] == "Astro 发布"
    assert frontmatter["description"] == "Astro 发布说明"
    assert frontmatter["slug"] == "astro-publish"
    assert frontmatter["layout"] == "post"
    assert frontmatter["draft"] is False


def test_build_frontmatter_accepts_json_text_template():
    config = {
        "default_frontmatter_template": '{\n  "draft": false,\n  "layout": "post"\n}',
        "required_frontmatter_fields": ["title", "description", "pubDate", "slug"],
    }
    request = BlogGenerateRequest(topic="Astro 发布")
    draft = AstroArticleDraft(
        title="Astro 发布",
        description="Astro 发布说明",
        body="# Demo",
        slug="astro-publish",
    )

    frontmatter = build_frontmatter(config, request, draft)

    assert frontmatter["layout"] == "post"
    assert frontmatter["draft"] is False
