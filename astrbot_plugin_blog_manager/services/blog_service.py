"""High-level orchestration for draft generation and publishing."""

from __future__ import annotations

from typing import Any, Mapping

from ..adapters.astro_adapter import AstroAdapter
from ..adapters.frontmatter_adapter import build_frontmatter
from ..constants import DEFAULT_REQUIRED_FRONTMATTER_FIELDS
from ..exceptions import AstroValidationError, PluginConfigError
from ..models import (
    ArticleSummary,
    AstroArticleDraft,
    BlogGenerateRequest,
    DeleteResult,
    PublishResult,
    PullRequestMergeResult,
)
from ..utils.markdown import render_markdown_document
from ..validators.astro_validator import AstroValidator
from .agent_service import AgentService
from .publish_service import PublishService


class BlogService:
    """Coordinates generation, validation and publication workflows."""

    def __init__(self, context: Any, config: Mapping[str, Any]):
        self.context = context
        self.config = config
        self.agent_service = AgentService(context, config)
        self.publish_service = PublishService(config)
        self.adapter = AstroAdapter(config)
        self.validator = AstroValidator(config)

    def config_check(self) -> list[str]:
        required_keys = [
            "github_token",
            "github_owner",
            "github_repo",
            "default_branch",
            "content_dir",
            "article_format",
            "image_mode",
        ]
        lines = []
        for key in required_keys:
            value = self.config.get(key, "")
            state = "OK" if value not in ("", None, []) else "MISSING"
            lines.append(f"{key}: {state}")
        lines.append(
            "repo_target: "
            f"{self.config.get('github_owner', '')}/{self.config.get('github_repo', '')}"
        )
        lines.append(f"default_branch_value: {self.config.get('default_branch', '')}")
        lines.append(f"write_mode_value: {self.config.get('write_mode', '')}")
        required_frontmatter = self.config.get(
            "required_frontmatter_fields", DEFAULT_REQUIRED_FRONTMATTER_FIELDS
        )
        lines.append(f"required_frontmatter_fields: {required_frontmatter}")
        return lines

    async def generate_draft(
        self,
        request: BlogGenerateRequest,
        *,
        event: Any | None = None,
    ) -> AstroArticleDraft:
        draft = await self.agent_service.generate_article(request, event=event)
        draft.article_path = self.adapter.build_article_path(draft)
        draft.frontmatter = build_frontmatter(self.config, request, draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        self._ensure_valid(draft)
        return draft

    async def publish(
        self,
        request: BlogGenerateRequest,
        *,
        event: Any | None = None,
    ) -> PublishResult:
        self._ensure_github_ready()
        draft = await self.generate_draft(request, event=event)
        return await self.publish_service.publish(request, draft)

    async def list_articles(self, *, limit: int = 10) -> list[ArticleSummary]:
        self._ensure_github_ready()
        return await self.publish_service.list_articles(limit=limit)

    async def merge_pull_request(
        self,
        *,
        pr_number: int,
        method: str = "squash",
    ) -> PullRequestMergeResult:
        self._ensure_github_ready()
        return await self.publish_service.merge_pull_request(
            pr_number=pr_number,
            method=method,
        )

    async def delete_article(self, *, target: str) -> DeleteResult:
        self._ensure_github_ready()
        return await self.publish_service.delete_article(target=target)

    async def update_article(
        self,
        *,
        target: str,
        instructions: str,
        event: Any | None = None,
    ) -> PublishResult:
        self._ensure_github_ready()
        article, existing_content = await self.publish_service.get_article(target=target)
        request = BlogGenerateRequest(
            topic=article.title,
            instructions=(
                f"请基于现有文章进行更新，保留文章主题与路径 slug，不要新建文章。"
                f"更新要求：{instructions}"
            ),
            immediate_publish=True,
        )
        draft = await self.agent_service.generate_article(
            request,
            event=event,
            existing_article=existing_content,
            fixed_slug=article.slug,
        )
        draft.slug = article.slug
        draft.article_path = article.path
        draft.frontmatter = build_frontmatter(self.config, request, draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        self._ensure_valid(draft)
        return await self.publish_service.update_article(
            request,
            draft,
            article_path=article.path,
        )

    def validate_rendered_article(self, content: str, slug: str = "manual-check") -> list[str]:
        draft = AstroArticleDraft(
            title="Manual Check",
            description="Manual Check",
            body=content,
            slug=slug,
            article_path=self.adapter.build_article_path(
                AstroArticleDraft(
                    title="Manual Check",
                    description="Manual Check",
                    body=content,
                    slug=slug,
                )
            ),
            frontmatter={
                "title": "Manual Check",
                "description": "Manual Check",
                "pubDate": "2026-01-01T00:00:00+00:00",
                "slug": slug,
            },
            rendered_content=content,
        )
        result = self.validator.validate(draft)
        return [result.summary()]

    def _ensure_valid(self, draft: AstroArticleDraft) -> None:
        validation = self.validator.validate(draft)
        if not validation.valid:
            raise AstroValidationError(validation.summary())

    def _ensure_github_ready(self) -> None:
        for key in ("github_token", "github_owner", "github_repo"):
            if not str(self.config.get(key, "")).strip():
                raise PluginConfigError(f"缺少 GitHub 配置项: {key}")
