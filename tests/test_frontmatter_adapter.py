from datetime import date

from astrbot_plugin_blog_manager.adapters.frontmatter_adapter import build_frontmatter
from astrbot_plugin_blog_manager.models import AstroArticleDraft, BlogGenerateRequest


def test_build_frontmatter_merges_defaults_and_runtime_fields():
    config = {
        "default_frontmatter_template": {"draft": False, "layout": "post"},
        "required_frontmatter_fields": ["title", "published"],
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
    assert frontmatter["layout"] == "post"
    assert frontmatter["draft"] is False
    assert isinstance(frontmatter["published"], date)
    assert frontmatter["category"] == "技术"
    assert frontmatter["image"] == ""
    assert frontmatter["tags"] == ["astro", "blog"]


def test_build_frontmatter_accepts_json_text_template():
    config = {
        "default_frontmatter_template": '{\n  "draft": false,\n  "layout": "post"\n}',
        "required_frontmatter_fields": ["title", "published"],
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
    assert isinstance(frontmatter["published"], date)
    assert frontmatter["image"] == ""


def test_build_frontmatter_preserves_existing_published_and_sets_updated():
    config = {
        "default_frontmatter_template": {"draft": False, "comment": True},
        "required_frontmatter_fields": ["title", "published"],
    }
    request = BlogGenerateRequest(topic="更新文章")
    draft = AstroArticleDraft(
        title="更新文章",
        description="更新后的描述",
        body="# Demo",
        slug="update-post",
        tags=["更新", "博客"],
        frontmatter={
            "published": date(2026, 5, 1),
            "category": "随笔",
            "image": "https://example.com/cover.jpg",
        },
    )

    frontmatter = build_frontmatter(config, request, draft)

    assert frontmatter["published"] == date(2026, 5, 1)
    assert isinstance(frontmatter["updated"], date)
    assert frontmatter["category"] == "随笔"
    assert frontmatter["image"] == "https://example.com/cover.jpg"


def test_build_frontmatter_supports_legacy_required_fields():
    config = {
        "default_frontmatter_template": {"draft": False},
        "required_frontmatter_fields": ["title", "description", "pubDate", "slug"],
    }
    request = BlogGenerateRequest(topic="兼容旧配置")
    draft = AstroArticleDraft(
        title="兼容旧配置",
        description="兼容旧配置描述",
        body="# Demo",
        slug="legacy-compatible-post",
        tags=["兼容", "配置"],
    )

    frontmatter = build_frontmatter(config, request, draft)

    assert isinstance(frontmatter["published"], date)
    assert frontmatter["pubDate"] == frontmatter["published"].isoformat()
    assert frontmatter["slug"] == "legacy-compatible-post"


def test_build_frontmatter_normalizes_multiline_text_fields():
    config = {
        "default_frontmatter_template": {"draft": False, "category": "生活"},
        "required_frontmatter_fields": ["title", "published"],
    }
    request = BlogGenerateRequest(topic="标题")
    draft = AstroArticleDraft(
        title='星空下的约定: 夏夜\n散步',
        description="第一行\n第二行",
        body="# Demo",
        slug="starlight-promise",
        tags=["星空", "夏夜", "故事"],
        frontmatter={"image": " https://example.com/cover.jpg \n"},
    )

    frontmatter = build_frontmatter(config, request, draft)

    assert frontmatter["title"] == "星空下的约定: 夏夜 散步"
    assert frontmatter["description"] == "第一行 第二行"
    assert frontmatter["image"] == "https://example.com/cover.jpg"
