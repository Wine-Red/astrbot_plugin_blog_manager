from datetime import date

from astrbot_plugin_blog_manager.models import AstroArticleDraft
from astrbot_plugin_blog_manager.validators.astro_validator import AstroValidator


def test_validator_accepts_valid_draft():
    validator = AstroValidator(
        {
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
        }
    )
    draft = AstroArticleDraft(
        title="有效文章",
        description="描述",
        body="# Hello",
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
            "# Hello\n"
        ),
    )

    result = validator.validate(draft)

    assert result.valid is True
    assert result.issues == []


def test_validator_rejects_missing_fields_and_wrong_image_mode():
    validator = AstroValidator(
        {
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "download",
        }
    )
    draft = AstroArticleDraft(
        title="",
        description="",
        body="",
        slug="broken",
        article_path="src/content/posts/2026-01-01-broken.md",
        frontmatter={"title": "", "slug": "broken"},
        rendered_content="![x](https://example.com/image.png)",
    )

    result = validator.validate(draft)

    assert result.valid is False
    assert any(issue.field == "title" for issue in result.issues)
    assert any(issue.field == "description" for issue in result.issues)
    assert any(issue.field == "category" for issue in result.issues)
    assert any(issue.field == "tags" for issue in result.issues)
    assert any(issue.field == "image" for issue in result.issues)


def test_validator_rejects_rendered_frontmatter_missing_required_fields():
    validator = AstroValidator(
        {
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
        }
    )
    draft = AstroArticleDraft(
        title="有效文章",
        description="描述",
        body="# Hello",
        slug="valid-post",
        article_path="src/content/posts/2026-01-01-valid-post.md",
        frontmatter={
            "title": "有效文章",
            "description": "描述",
            "published": date(2026, 1, 1),
            "category": "技术",
            "tags": ["Astro", "博客"],
        },
        rendered_content="---\ntitle: 有效文章\n---\n\n# Hello\n",
    )

    result = validator.validate(draft)

    assert result.valid is False
    assert any(issue.field == "rendered_published" for issue in result.issues)


def test_validator_rejects_non_ascii_slug():
    validator = AstroValidator(
        {
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published", "slug"],
            "image_mode": "external",
        }
    )
    draft = AstroArticleDraft(
        title="中文标题",
        description="描述",
        body="# Hello",
        slug="中文标题",
        article_path="src/content/posts/2026-01-01-post.md",
        frontmatter={
            "title": "中文标题",
            "description": "描述",
            "published": date(2026, 1, 1),
            "slug": "中文标题",
            "category": "技术",
            "tags": ["Astro", "博客"],
        },
        rendered_content=(
            "---\n"
            "title: 中文标题\n"
            "description: 描述\n"
            "published: 2026-01-01\n"
            "slug: 中文标题\n"
            "category: 技术\n"
            "tags:\n"
            "- Astro\n"
            "- 博客\n"
            "---\n\n"
            "# Hello\n"
        ),
    )

    result = validator.validate(draft)

    assert result.valid is False
    assert any(issue.field == "slug" for issue in result.issues)
