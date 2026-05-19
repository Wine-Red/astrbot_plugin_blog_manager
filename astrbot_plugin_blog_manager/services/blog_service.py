"""High-level orchestration for draft generation and publishing."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

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
    DailyReportRequest,
    DeleteResult,
    NewsItem,
    PublishResult,
    PullRequestCloseResult,
    PullRequestMergeResult,
)
from ..utils.datetime_utils import frontmatter_date
from ..utils.markdown import parse_frontmatter, render_markdown_document
from ..validators.astro_validator import AstroValidator
from .agent_service import AgentService
from .publish_service import PublishService
from .search_service import (
    DEFAULT_AI_NEWS_QUERIES,
    SearchService,
    parse_news_items_from_text,
)


class BlogService:
    """Coordinates generation, validation and publication workflows."""

    def __init__(self, context: Any, config: Mapping[str, Any]):
        self.context = context
        self.config = config
        self.agent_service = AgentService(context, config)
        self.publish_service = PublishService(config)
        self.search_service = SearchService(bool(config.get("search_enabled", True)))
        self.search_service.context = context
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

    async def generate_daily_draft(
        self,
        *,
        event: Any | None = None,
        extra_instructions: str = "",
        report_date: date | None = None,
    ) -> AstroArticleDraft:
        news_items = await self._collect_daily_news(extra_instructions)
        request = DailyReportRequest(
            report_date=report_date or date.today(),
            extra_instructions=extra_instructions,
            immediate_publish=False,
        )
        cover_headline = news_items[0].title if news_items else "今日 AI 行业概览"
        cover_image_url = await self.agent_service.generate_cover_image(
            cover_headline,
            event=event,
        )
        draft = await self.agent_service.generate_daily_report(
            request,
            news_items,
            event=event,
            cover_image_url=cover_image_url,
        )
        draft.article_path = self.adapter.build_article_path(draft)
        draft.frontmatter = build_frontmatter(self.config, BlogGenerateRequest(topic=draft.title), draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        self._ensure_valid(draft)
        return draft

    async def publish_daily_report(
        self,
        *,
        event: Any | None = None,
        extra_instructions: str = "",
        report_date: date | None = None,
    ) -> PublishResult:
        self._ensure_github_ready()
        draft = await self.generate_daily_draft(
            event=event,
            extra_instructions=extra_instructions,
            report_date=report_date,
        )
        return await self.publish_service.publish(
            BlogGenerateRequest(
                topic=draft.title,
                instructions=extra_instructions,
                immediate_publish=True,
                image_preference="external",
            ),
            draft,
        )

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
        if not validation.valid:
            raise AstroValidationError(validation.summary())

    def _ensure_github_ready(self) -> None:
        for key in ("github_token", "github_owner", "github_repo"):
            if not str(self.config.get(key, "")).strip():
                raise PluginConfigError(f"缺少 GitHub 配置项: {key}")

    async def _collect_daily_news(self, extra_instructions: str = "") -> list[NewsItem]:
        supplied_items = parse_news_items_from_text(extra_instructions)
        try:
            news_items = await self.search_service.search_news(DEFAULT_AI_NEWS_QUERIES, limit=8)
        except Exception:
            news_items = []
        news_items = self._merge_news_items([*supplied_items, *news_items], limit=5)
        return news_items

    def _merge_news_items(self, items: list[NewsItem], *, limit: int) -> list[NewsItem]:
        merged: list[NewsItem] = []
        seen: set[str] = set()
        for item in items:
            key = item.url.strip() or item.title.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                break
        return merged

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
