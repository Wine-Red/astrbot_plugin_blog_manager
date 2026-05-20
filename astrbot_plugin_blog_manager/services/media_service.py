"""Remote image normalization and optional download support."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from ..adapters.astro_adapter import AstroAdapter
from ..exceptions import MediaDownloadError
from ..models import AstroArticleDraft, ImageAsset, RepoFileChange


class MediaService:
    """Prepare image assets for repository publishing."""

    def __init__(self, config: Mapping[str, Any]):
        self.config = config
        self.adapter = AstroAdapter(config)

    async def prepare_assets(self, draft: AstroArticleDraft) -> tuple[AstroArticleDraft, list[RepoFileChange], list[str]]:
        changes: list[RepoFileChange] = []
        prepared_paths: set[str] = set()
        for asset in draft.images:
            if asset.data and asset.repo_path:
                changes.append(
                    RepoFileChange(
                        path=asset.repo_path,
                        content=asset.data,
                        message=f"Add blog asset: {asset.repo_path}",
                    )
                )
                prepared_paths.add(asset.repo_path)

        image_mode = str(self.config.get("image_mode", "external"))
        if image_mode != "download":
            return draft, changes, []

        warnings: list[str] = []
        for asset in draft.images:
            if asset.repo_path in prepared_paths:
                continue
            if not asset.source_url.startswith("http"):
                warnings.append(f"跳过非远程图片: {asset.source_url}")
                continue
            try:
                prepared = await self._download_asset(asset, draft)
            except MediaDownloadError as exc:
                warnings.append(str(exc))
                continue

            asset.repo_path = prepared.repo_path
            changes.append(
                RepoFileChange(
                    path=prepared.repo_path,
                    content=prepared.data,
                    message=f"Add blog asset: {prepared.repo_path}",
                )
            )
            draft.body = draft.body.replace(prepared.source_url, "/" + prepared.repo_path)
            if draft.frontmatter.get("image") == prepared.source_url:
                draft.frontmatter["image"] = "/" + prepared.repo_path
            if draft.rendered_content:
                draft.rendered_content = draft.rendered_content.replace(
                    prepared.source_url, "/" + prepared.repo_path
                )
        return draft, changes, warnings

    async def _download_asset(self, asset: ImageAsset, draft: AstroArticleDraft) -> ImageAsset:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(asset.source_url)
        except httpx.HTTPError as exc:
            raise MediaDownloadError(f"图片下载失败: {asset.source_url} -> {exc}") from exc

        if response.status_code >= 400:
            raise MediaDownloadError(f"图片下载失败: {asset.source_url} -> HTTP {response.status_code}")

        asset.data = response.content
        asset.content_type = response.headers.get("content-type", "image/png")
        asset.repo_path = self.adapter.build_asset_path(asset, draft)
        return asset
