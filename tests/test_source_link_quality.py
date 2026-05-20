from datetime import date

import pytest

from astrbot_plugin_blog_manager.exceptions import AstroValidationError
from astrbot_plugin_blog_manager.models import AstroArticleDraft
from astrbot_plugin_blog_manager.services.blog_service import BlogService
from astrbot_plugin_blog_manager.utils.markdown import extract_markdown_links


def _valid_draft(body: str) -> AstroArticleDraft:
    return AstroArticleDraft(
        title="有效文章",
        description="描述",
        body=body,
        slug="valid-post",
        article_path="src/content/posts/2026-01-01-valid-post.md",
        frontmatter={
            "title": "有效文章",
            "description": "描述",
            "published": date(2026, 1, 1),
            "category": "技术",
            "tags": ["Astro", "博客"],
        },
        rendered_content=(
            "---\n"
            "title: 有效文章\n"
            "description: 描述\n"
            "published: 2026-01-01\n"
            "category: 技术\n"
            "tags:\n"
            "- Astro\n"
            "- 博客\n"
            "---\n\n"
            f"{body}\n"
        ),
    )


def test_extract_markdown_links_ignores_images():
    text = "[来源](https://example.com/news) ![封面](https://example.com/image.png)"

    assert extract_markdown_links(text) == [("来源", "https://example.com/news")]


def test_blog_service_rejects_placeholder_source_links():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
        },
    )
    draft = _valid_draft("参考来源：[来源](https://example.com/news)")

    with pytest.raises(AstroValidationError) as exc_info:
        service._ensure_valid(draft)

    assert "来源链接疑似占位或伪造" in str(exc_info.value)


def test_blog_service_allows_realistic_source_links():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
        },
    )
    draft = _valid_draft("参考来源：[OpenAI 官方博客](https://openai.com/blog/example)")

    service._ensure_valid(draft)
