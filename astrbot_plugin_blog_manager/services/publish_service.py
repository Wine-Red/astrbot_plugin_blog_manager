"""Publish Astro drafts to GitHub repositories."""

from __future__ import annotations

from typing import Any, Mapping

from ..adapters.astro_adapter import AstroAdapter
from ..adapters.frontmatter_adapter import build_frontmatter
from ..clients.github_client import GitHubClient
from ..exceptions import PluginConfigError
from ..models import (
    ArticleSummary,
    AstroArticleDraft,
    BlogGenerateRequest,
    DeleteResult,
    PublishResult,
    PullRequestCloseResult,
    PullRequestMergeResult,
)
from ..utils.markdown import render_markdown_document
from .media_service import MediaService
from .repository_service import RepositoryService


class PublishService:
    """Turns a validated draft into GitHub commits or PRs."""

    def __init__(self, config: Mapping[str, Any]):
        self.config = config
        self.adapter = AstroAdapter(config)
        self.media_service = MediaService(config)

    async def publish(
        self,
        request: BlogGenerateRequest,
        draft: AstroArticleDraft,
    ) -> PublishResult:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        if not draft.frontmatter:
            draft.frontmatter = build_frontmatter(self.config, request, draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        draft.article_path = self.adapter.build_article_path(draft)
        draft, media_changes, warnings = await self.media_service.prepare_assets(draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        result = await repository_service.publish_article(
            article_path=draft.article_path,
            article_title=draft.title,
            slug=draft.slug,
            article_content=draft.rendered_content.encode("utf-8"),
            extra_changes=media_changes,
        )
        result.warnings.extend(draft.warnings)
        result.warnings.extend(warnings)
        site_base_url = str(self.config.get("site_base_url", "/")).rstrip("/")
        if site_base_url:
            result.article_url = f"{site_base_url}/{draft.slug}"
        return result

    def _build_client(self) -> GitHubClient:
        token = str(self.config.get("github_token", "")).strip()
        owner = str(self.config.get("github_owner", "")).strip()
        repo = str(self.config.get("github_repo", "")).strip()
        if not token or not owner or not repo:
            raise PluginConfigError("GitHub 配置不完整，至少需要 github_token/github_owner/github_repo。")
        return GitHubClient(token=token, owner=owner, repo=repo)

    async def merge_pull_request(
        self,
        *,
        pr_number: int,
        method: str = "squash",
    ) -> PullRequestMergeResult:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        return await repository_service.merge_pull_request(number=pr_number, method=method)

    async def close_pull_request(self, *, pr_number: int) -> PullRequestCloseResult:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        return await repository_service.close_pull_request(number=pr_number)

    async def delete_article(self, *, target: str) -> DeleteResult:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        return await repository_service.delete_article(target=target)

    async def list_articles(self, *, limit: int = 10) -> list[ArticleSummary]:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        return await repository_service.list_articles(limit=limit)

    async def get_article(self, *, target: str) -> tuple[ArticleSummary, str]:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        return await repository_service.get_article(target=target)

    async def update_article(
        self,
        request: BlogGenerateRequest,
        draft: AstroArticleDraft,
        *,
        article_path: str,
    ) -> PublishResult:
        client = self._build_client()
        await client.verify_repository_access(
            str(self.config.get("default_branch", "main")).strip() or "main"
        )
        repository_service = RepositoryService(client, self.config)
        if not draft.frontmatter:
            draft.frontmatter = build_frontmatter(self.config, request, draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        draft.article_path = article_path
        draft, media_changes, warnings = await self.media_service.prepare_assets(draft)
        draft.rendered_content = render_markdown_document(draft.frontmatter, draft.body)
        result = await repository_service.update_article(
            article_path=draft.article_path,
            article_title=draft.title,
            slug=draft.slug,
            article_content=draft.rendered_content.encode("utf-8"),
            extra_changes=media_changes,
        )
        result.warnings.extend(draft.warnings)
        result.warnings.extend(warnings)
        site_base_url = str(self.config.get("site_base_url", "/")).rstrip("/")
        if site_base_url:
            result.article_url = f"{site_base_url}/{draft.slug}"
        return result
