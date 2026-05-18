"""Publish Astro drafts to GitHub repositories."""

from __future__ import annotations

from typing import Any, Mapping

from ..adapters.astro_adapter import AstroAdapter
from ..adapters.frontmatter_adapter import build_frontmatter
from ..clients.github_client import GitHubClient
from ..exceptions import PluginConfigError
from ..models import AstroArticleDraft, BlogGenerateRequest, PublishResult
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
