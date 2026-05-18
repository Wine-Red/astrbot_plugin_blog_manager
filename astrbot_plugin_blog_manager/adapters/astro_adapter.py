"""Astro repository path and output helpers."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Mapping

from ..constants import (
    DEFAULT_ARTICLE_FORMAT,
    DEFAULT_ASSET_DIR,
    DEFAULT_CONTENT_DIR,
    SUPPORTED_ARTICLE_FORMATS,
)
from ..models import AstroArticleDraft, ImageAsset
from ..utils.datetime_utils import date_path_fragment
from ..utils.slug import slugify


class AstroAdapter:
    """Transforms a draft into repository paths expected by Astro projects."""

    def __init__(self, config: Mapping[str, Any]):
        self.config = config

    def article_extension(self) -> str:
        article_format = str(
            self.config.get("article_format", DEFAULT_ARTICLE_FORMAT)
        ).lower()
        if article_format not in SUPPORTED_ARTICLE_FORMATS:
            article_format = DEFAULT_ARTICLE_FORMAT
        return article_format

    def build_article_path(self, draft: AstroArticleDraft) -> str:
        content_dir = str(self.config.get("content_dir", DEFAULT_CONTENT_DIR)).strip("/")
        slug = slugify(draft.slug or draft.title)
        suffix = self.article_extension()
        return PurePosixPath(content_dir, f"{date_path_fragment()}-{slug}.{suffix}").as_posix()

    def build_asset_path(self, asset: ImageAsset, draft: AstroArticleDraft) -> str:
        asset_dir = str(self.config.get("asset_dir", DEFAULT_ASSET_DIR)).strip("/")
        slug = slugify(draft.slug or draft.title)
        base_name = slugify(asset.suggested_name or asset.alt_text or slug, default=slug)
        extension = ".png"
        if asset.content_type:
            if "jpeg" in asset.content_type:
                extension = ".jpg"
            elif "webp" in asset.content_type:
                extension = ".webp"
            elif "gif" in asset.content_type:
                extension = ".gif"
        return PurePosixPath(asset_dir, slug, f"{base_name}{extension}").as_posix()
