"""Helpers shared by command and LLM tool entrypoints."""

from __future__ import annotations

from typing import Any

from ..models import (
    ArticleSummary,
    AstroArticleDraft,
    BlogGenerateRequest,
    DeleteResult,
    PublishResult,
    PullRequestCloseResult,
    PullRequestMergeResult,
)


def parse_blog_command(message_text: str) -> tuple[str, str]:
    """Parse `/blog <subcommand> <payload>` style text."""

    parts = message_text.strip().split(maxsplit=2)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "help", ""
    if len(parts) == 2:
        return parts[1].lower(), ""
    return parts[1].lower(), parts[2].strip()


def build_request_from_payload(
    topic: str,
    *,
    instructions: str = "",
    immediate_publish: bool = False,
    image_preference: str = "auto",
) -> BlogGenerateRequest:
    """Normalize tool arguments into the service request object."""

    return BlogGenerateRequest(
        topic=topic.strip(),
        instructions=instructions.strip(),
        immediate_publish=immediate_publish,
        image_preference=image_preference,
    )


def format_draft_summary(draft: AstroArticleDraft) -> str:
    """Return a compact draft summary for QQ replies."""

    lines = [
        "草稿已生成。",
        f"标题: {draft.title}",
        f"Slug: {draft.slug}",
        f"文章路径: {draft.article_path}",
        f"标签: {', '.join(draft.tags) if draft.tags else '无'}",
    ]
    if draft.images:
        lines.append(f"图片数量: {len(draft.images)}")
    return "\n".join(lines)


def format_publish_summary(result: PublishResult) -> str:
    """Return a compact publish summary for QQ replies."""

    return "发布完成。\n" + "\n".join(result.to_lines())


def format_merge_summary(result: PullRequestMergeResult) -> str:
    """Return a compact merge summary for QQ replies."""

    return "PR 合并完成。\n" + "\n".join(result.to_lines())


def format_close_summary(result: PullRequestCloseResult) -> str:
    """Return a compact close summary for QQ replies."""

    return "PR 已关闭。\n" + "\n".join(result.to_lines())


def format_delete_summary(result: DeleteResult) -> str:
    """Return a compact delete summary for QQ replies."""

    return "文章删除完成。\n" + "\n".join(result.to_lines())


def format_list_summary(items: list[ArticleSummary]) -> str:
    """Return a compact article list."""

    if not items:
        return "未找到文章。"
    lines = ["文章列表："]
    lines.extend(item.to_line() for item in items)
    return "\n".join(lines)


def format_help_text() -> str:
    """Help text for the `/blog` command."""

    return "\n".join(
        [
            "用法:",
            "/blog publish <主题或要求>",
            "/blog draft <主题或要求>",
            "/blog list [数量]",
            "/blog update <slug或完整路径> <更新要求>",
            "/blog merge <PR编号> [merge|squash|rebase]",
            "/blog close <PR编号>",
            "/blog delete <slug或完整路径>",
            "/blog check <Markdown 草稿>",
            "/blog config-check",
        ]
    )


def extract_tool_string(value: Any, default: str = "") -> str:
    """Normalize tool arguments that may be None or non-strings."""

    if value is None:
        return default
    return str(value).strip()
