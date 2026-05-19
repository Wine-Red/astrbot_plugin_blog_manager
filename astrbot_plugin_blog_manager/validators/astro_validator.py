"""Astro content pre-validator."""

from __future__ import annotations
from datetime import date

from pathlib import PurePosixPath
import re
from typing import Any, Mapping

import yaml

from ..constants import DEFAULT_CONTENT_DIR
from ..models import AstroArticleDraft, ValidationIssue, ValidationResult
from ..utils.markdown import extract_image_urls, parse_frontmatter


ASCII_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AstroValidator:
    """Performs strict plugin-side validation before publishing to GitHub."""

    def __init__(self, config: Mapping[str, Any]):
        self.config = config

    def validate(self, draft: AstroArticleDraft) -> ValidationResult:
        issues: list[ValidationIssue] = []
        required_fields = self.config.get("required_frontmatter_fields", [])
        if not isinstance(required_fields, list):
            required_fields = []

        if not draft.title.strip():
            issues.append(ValidationIssue("title", "标题不能为空。"))
        if not draft.description.strip():
            issues.append(ValidationIssue("description", "描述不能为空。"))
        if not draft.body.strip():
            issues.append(ValidationIssue("body", "正文不能为空。"))
        if not ASCII_SLUG_PATTERN.fullmatch(draft.slug):
            issues.append(
                ValidationIssue("slug", "slug 只能使用 ASCII 小写字母、数字和连字符。")
            )
        tags = draft.frontmatter.get("tags", [])
        if not isinstance(tags, list) or not [tag for tag in tags if str(tag).strip()]:
            issues.append(ValidationIssue("tags", "至少需要一个标签。"))
        category = draft.frontmatter.get("category", "")
        if not str(category).strip():
            issues.append(ValidationIssue("category", "分类不能为空。"))
        if not draft.article_path.strip():
            issues.append(ValidationIssue("article_path", "文章路径不能为空。"))
        else:
            content_dir = str(self.config.get("content_dir", DEFAULT_CONTENT_DIR)).strip("/")
            article_path = PurePosixPath(draft.article_path)
            expected_root = PurePosixPath(content_dir)
            if expected_root not in article_path.parents:
                issues.append(
                    ValidationIssue("article_path", "文章路径必须位于配置的 content_dir 下。")
                )

        for field_name in required_fields:
            value = draft.frontmatter.get(field_name)
            if value in ("", None, []):
                issues.append(
                    ValidationIssue(str(field_name), "frontmatter 缺少必填字段或字段为空。")
                )

        published = draft.frontmatter.get("published")
        if published is not None and not isinstance(published, date):
            issues.append(ValidationIssue("published", "published 必须是日期。"))
        updated = draft.frontmatter.get("updated")
        if updated is not None and not isinstance(updated, date):
            issues.append(ValidationIssue("updated", "updated 必须是日期。"))
        slug = draft.frontmatter.get("slug")
        if slug is not None:
            if not isinstance(slug, str):
                issues.append(ValidationIssue("slug", "slug 必须是字符串。"))
            elif not ASCII_SLUG_PATTERN.fullmatch(slug):
                issues.append(
                    ValidationIssue("slug", "frontmatter slug 只能使用 ASCII 小写字母、数字和连字符。")
                )

        try:
            yaml.safe_dump(draft.frontmatter, allow_unicode=True, sort_keys=False)
        except yaml.YAMLError as exc:
            issues.append(ValidationIssue("frontmatter", f"frontmatter YAML 序列化失败: {exc}"))

        rendered_frontmatter = parse_frontmatter(draft.rendered_content)
        if draft.rendered_content and not rendered_frontmatter:
            issues.append(ValidationIssue("rendered_frontmatter", "最终渲染的 Markdown 缺少可解析的 frontmatter。"))
        elif rendered_frontmatter:
            for field_name in required_fields:
                value = rendered_frontmatter.get(field_name)
                if value in ("", None, []):
                    issues.append(
                        ValidationIssue(
                            f"rendered_{field_name}",
                            "最终渲染的 frontmatter 缺少必填字段或字段为空。",
                        )
                    )

        image_mode = str(self.config.get("image_mode", "external"))
        for url in extract_image_urls(draft.rendered_content or draft.body):
            if image_mode == "download" and url.startswith("http"):
                issues.append(
                    ValidationIssue("image", "download 模式下不应保留外链图片引用。")
                )
            if image_mode == "external" and not (
                url.startswith("http") or url.startswith("/")
            ):
                issues.append(
                    ValidationIssue("image", "external 模式下图片应使用站点路径或外链 URL。")
                )

        return ValidationResult(valid=not issues, issues=issues)
