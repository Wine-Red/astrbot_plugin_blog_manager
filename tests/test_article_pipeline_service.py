from datetime import date

import pytest

from astrbot_plugin_blog_manager.exceptions import AstroValidationError
from astrbot_plugin_blog_manager.models import AstroArticleDraft, BlogGenerateRequest
from astrbot_plugin_blog_manager.services.article_pipeline_service import ArticlePipelineService
from astrbot_plugin_blog_manager.services.blog_service import BlogService


def test_pipeline_infers_required_sources_for_news_like_topics():
    service = ArticlePipelineService()
    request = BlogGenerateRequest(topic="今日大模型 Agent 产品发布")

    spec = service.build_request_spec(request)

    assert spec.article_type == "news_explain"
    assert spec.source_policy == "required"
    assert spec.image_policy == "required"


def test_pipeline_collects_and_scores_official_sources():
    service = ArticlePipelineService()
    request = BlogGenerateRequest(topic="OpenAI API 发布")
    draft = AstroArticleDraft(
        title="OpenAI API 发布",
        description="desc",
        body="参考来源：[OpenAI 官方博客](https://openai.com/blog/example)",
        slug="openai-api-release",
    )

    result = service.process(request, draft)

    assert result.issues == []
    assert len(result.sources) == 1
    assert result.sources[0].source_type == "official"
    assert result.sources[0].reliability >= 80
    assert result.evidence[0].confidence == "high"


def test_pipeline_rejects_missing_required_sources():
    service = ArticlePipelineService()
    request = BlogGenerateRequest(topic="今日大模型 Agent 产品发布")
    draft = AstroArticleDraft(
        title="今日大模型 Agent 产品发布",
        description="desc",
        body="# Hello",
        slug="agent-product-release",
    )

    result = service.process(request, draft)

    assert any(issue.field == "source" for issue in result.issues)


def test_pipeline_rejects_placeholder_images():
    service = ArticlePipelineService()
    request = BlogGenerateRequest(topic="Astro 图片发布")
    draft = AstroArticleDraft(
        title="Astro 图片发布",
        description="desc",
        body="![架构图](https://example.com/image.png)",
        slug="astro-image-publish",
        frontmatter={"image": "https://example.com/cover.png"},
    )

    result = service.process(request, draft)

    assert any(issue.field == "image" for issue in result.issues)


def test_blog_service_runs_pipeline_before_validation():
    service = BlogService(
        context=None,
        config={
            "content_dir": "src/content/posts",
            "required_frontmatter_fields": ["title", "published"],
            "image_mode": "external",
        },
    )
    request = BlogGenerateRequest(topic="今日大模型 Agent 产品发布")
    draft = AstroArticleDraft(
        title="今日大模型 Agent 产品发布",
        description="desc",
        body="# Hello",
        slug="agent-product-release",
        article_path="src/content/posts/2026-01-01-agent-product-release.md",
        frontmatter={
            "title": "今日大模型 Agent 产品发布",
            "description": "desc",
            "published": date(2026, 1, 1),
            "category": "技术",
            "tags": ["AI"],
        },
    )

    with pytest.raises(AstroValidationError) as exc_info:
        service._run_pipeline(request, draft)

    assert "该主题需要可靠来源" in str(exc_info.value)
