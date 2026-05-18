"""Build Astro-compatible frontmatter from configuration and runtime inputs."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

import yaml

from ..constants import DEFAULT_FRONTMATTER_TEMPLATE
from ..models import AstroArticleDraft, BlogGenerateRequest
from ..utils.datetime_utils import iso_pub_date


def _normalize_required_fields(config: Mapping[str, Any]) -> list[str]:
    raw = config.get("required_frontmatter_fields", [])
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


def _parse_template_config(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return deepcopy(raw)
    if not isinstance(raw, str) or not raw.strip():
        return deepcopy(DEFAULT_FRONTMATTER_TEMPLATE)

    text = raw.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            return deepcopy(DEFAULT_FRONTMATTER_TEMPLATE)

    if isinstance(parsed, dict):
        return deepcopy(parsed)
    return deepcopy(DEFAULT_FRONTMATTER_TEMPLATE)


def build_frontmatter(
    config: Mapping[str, Any],
    request: BlogGenerateRequest,
    draft: AstroArticleDraft,
) -> dict[str, Any]:
    """Merge template defaults and generated article metadata."""

    template = _parse_template_config(config.get("default_frontmatter_template"))

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
