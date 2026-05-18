"""Build Astro-compatible frontmatter from configuration and runtime inputs."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Mapping

import yaml

from ..constants import DEFAULT_FRONTMATTER_TEMPLATE
from ..models import AstroArticleDraft, BlogGenerateRequest
from ..utils.datetime_utils import frontmatter_date


def _normalize_required_fields(config: Mapping[str, Any]) -> list[str]:
    raw = config.get("required_frontmatter_fields", [])
    if isinstance(raw, list):
        normalized: list[str] = []
        for item in raw:
            field_name = str(item).strip()
            if not field_name:
                continue
            if field_name == "pubDate":
                field_name = "published"
            if field_name not in normalized:
                normalized.append(field_name)
        return normalized
    return []


def _raw_required_fields(config: Mapping[str, Any]) -> list[str]:
    raw = config.get("required_frontmatter_fields", [])
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
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


def _normalize_frontmatter_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None
    return None


def _yaml_safe_inline_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())


def build_frontmatter(
    config: Mapping[str, Any],
    request: BlogGenerateRequest,
    draft: AstroArticleDraft,
) -> dict[str, Any]:
    """Merge template defaults and generated article metadata."""

    template = _parse_template_config(config.get("default_frontmatter_template"))
    generated_frontmatter = deepcopy(draft.frontmatter) if isinstance(draft.frontmatter, dict) else {}
    template.update(generated_frontmatter)
    raw_required_fields = _raw_required_fields(config)

    published = _normalize_frontmatter_date(generated_frontmatter.get("published"))
    is_update = published is not None
    if published is None:
        published = frontmatter_date()

    category = _yaml_safe_inline_text(generated_frontmatter.get("category", "")) or _yaml_safe_inline_text(
        template.get("category", "技术")
    ) or "技术"
    image = _yaml_safe_inline_text(generated_frontmatter.get("image", template.get("image", "")))
    tags = draft.tags or generated_frontmatter.get("tags") or ["AstrBot", "博客", "Astro"]
    normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not normalized_tags:
        normalized_tags = ["AstrBot", "博客", "Astro"]

    template.update(
        {
            "title": _yaml_safe_inline_text(draft.title),
            "description": _yaml_safe_inline_text(draft.description),
            "published": published,
            "tags": normalized_tags,
            "category": category,
            "image": image,
        }
    )
    template.setdefault("author", "AstrBot")
    template.setdefault("draft", False)
    template.setdefault("comment", True)
    template.setdefault("pinned", False)
    if "pubDate" in raw_required_fields or "pubDate" in template:
        template["pubDate"] = published.isoformat()
    if "slug" in raw_required_fields or "slug" in template:
        template["slug"] = draft.slug
    if is_update:
        template["updated"] = frontmatter_date()

    required = _normalize_required_fields(config)
    for field_name in required:
        fallback = generated_frontmatter.get(field_name, "")
        if field_name == "published" and not fallback:
            fallback = published
        template.setdefault(field_name, fallback)
    return template
