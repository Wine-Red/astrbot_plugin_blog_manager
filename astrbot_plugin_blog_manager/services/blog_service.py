"""High-level orchestration for draft generation and publishing."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlparse

from ..adapters.astro_adapter import AstroAdapter
from ..adapters.frontmatter_adapter import build_frontmatter
from ..constants import (
    DEFAULT_REQUIRED_FRONTMATTER_FIELDS,
    SUPPORTED_ARTICLE_FORMATS,
    SUPPORTED_IMAGE_MODES,
    SUPPORTED_WRITE_MODES,
)
from ..exceptions import AstroValidationError, PluginConfigError
from ..models import (
    ArticleSummary,
    AstroArticleDraft,
    BlogGenerateRequest,
    DeleteResult,
    PublishResult,
    PullRequestCloseResult,
    PullRequestMergeResult,
    ValidationIssue,
)
from ..utils.datetime_utils import frontmatter_date
from ..utils.markdown import extract_markdown_links, parse_frontmatter, render_markdown_document
from ..validators.astro_validator import AstroValidator
from .agent_service import AgentService
from .article_pipeline_service import ArticlePipelineService
from .image_generation_service import ImageGenerationService
from .publish_service import PublishService


SUSPICIOUS_SOURCE_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "test.com",
    "test.org",
    "invalid.com",
}


class BlogService:
    """Coordinates generation, validation and publication workflows."""

    def __init__(self, context: Any, config: Mapping[str, Any]):
        self.context = context
        self.config = config
        self.agent_service = AgentService(context, config)
        self.pipeline_service = ArticlePipelineService(
            allow_generated_sources=bool(config.get("allow_generated_sources", False))
        )
        self.image_generation_service = ImageGenerationService(config)
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
        lines.extend(
            self._option_check_lines(
                {
                    "write_mode": SUPPORTED_WRITE_MODES,
                    "article_format": SUPPORTED_ARTICLE_FORMATS,
                    "image_mode": SUPPORTED_IMAGE_MODES,
                }
            )
        )
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
        await self.image_generation_service.ensure_cover_image(request, draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        self._run_pipeline(request, draft)
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

    async def close_pull_request(self, *, pr_number: int) -> PullRequestCloseResult:
        self._ensure_github_ready()
        return await self.publish_service.close_pull_request(pr_number=pr_number)

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
        existing_frontmatter = parse_frontmatter(existing_content)
        if existing_frontmatter:
            draft.frontmatter = existing_frontmatter
        draft.frontmatter = build_frontmatter(self.config, request, draft)
        await self.image_generation_service.ensure_cover_image(request, draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        self._run_pipeline(request, draft)
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
                "published": frontmatter_date(),
                "category": "技术",
                "tags": ["检查", "草稿"],
            },
            rendered_content=content,
        )
        result = self.validator.validate(draft)
        return [result.summary()]

    def _ensure_valid(self, draft: AstroArticleDraft) -> None:
        validation = self.validator.validate(draft)
        validation.issues.extend(self._source_link_issues(draft))
        if validation.issues:
            raise AstroValidationError(
                "\n".join(f"- {issue.field}: {issue.message}" for issue in validation.issues)
            )

    def _run_pipeline(self, request: BlogGenerateRequest, draft: AstroArticleDraft) -> None:
        result = self.pipeline_service.process(request, draft)
        draft.warnings.extend(result.warnings)
        if result.issues:
            raise AstroValidationError(
                "\n".join(f"- {issue.field}: {issue.message}" for issue in result.issues)
            )

    def _ensure_github_ready(self) -> None:
        for key in ("github_token", "github_owner", "github_repo"):
            if not str(self.config.get(key, "")).strip():
                raise PluginConfigError(f"缺少 GitHub 配置项: {key}")

    def _source_link_issues(self, draft: AstroArticleDraft) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for label, url in extract_markdown_links(draft.rendered_content or draft.body):
            if not self._is_source_like_link(label, url):
                continue
            if self._is_suspicious_source_url(url):
                issues.append(
                    ValidationIssue(
                        "source",
                        f"来源链接疑似占位或伪造，请替换为真实可核验来源: {url}",
                    )
                )
        return issues

    def _is_source_like_link(self, label: str, url: str) -> bool:
        source_markers = ("来源", "参考", "原文", "官方", "报道", "source", "reference")
        text = f"{label} {url}".lower()
        return any(marker in text for marker in source_markers)

    def _is_suspicious_source_url(self, url: str) -> bool:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.netloc.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname in SUSPICIOUS_SOURCE_DOMAINS:
            return True
        return ".invalid" in hostname or hostname.endswith(".test")

    def _option_check_lines(self, options: Mapping[str, set[str]]) -> list[str]:
        lines: list[str] = []
        for key, supported_values in options.items():
            value = str(self.config.get(key, "")).strip().lower()
            if not value:
                continue
            if value not in supported_values:
                lines.append(
                    f"{key}_valid: INVALID，应为 {', '.join(sorted(supported_values))} 之一"
                )
        return lines
