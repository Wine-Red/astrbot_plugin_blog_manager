"""Build Astro-compatible frontmatter from configuration and runtime inputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ..constants import DEFAULT_FRONTMATTER_TEMPLATE
from ..models import AstroArticleDraft, BlogGenerateRequest
from ..utils.datetime_utils import iso_pub_date


def _normalize_required_fields(config: Mapping[str, Any]) -> list[str]:
    raw = config.get("required_frontmatter_fields", [])
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


def build_frontmatter(
    config: Mapping[str, Any],
    request: BlogGenerateRequest,
    draft: AstroArticleDraft,
) -> dict[str, Any]:
    """Merge template defaults and generated article metadata."""

    template = config.get("default_frontmatter_template") or DEFAULT_FRONTMATTER_TEMPLATE
    if not isinstance(template, dict):
        template = deepcopy(DEFAULT_FRONTMATTER_TEMPLATE)
    else:
        template = deepcopy(template)

    template.update(
        {
            "title": draft.title,
            "description": draft.description,
            "pubDate": draft.frontmatter.get("pubDate", iso_pub_date()),
            "slug": draft.slug,
            "tags": draft.tags,
        }
    )
    template.setdefault("author", "AstrBot")
    template.setdefault("draft", False)
    template.setdefault("topic", request.topic)
    if request.audience:
        template.setdefault("audience", request.audience)

    required = _normalize_required_fields(config)
    for field_name in required:
        template.setdefault(field_name, draft.frontmatter.get(field_name, ""))
    return template
