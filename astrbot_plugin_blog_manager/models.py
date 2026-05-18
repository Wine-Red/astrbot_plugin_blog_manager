"""Data models used across the plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BlogGenerateRequest:
    """Normalized user request for generating a blog article."""

    topic: str
    instructions: str = ""
    audience: str = "通用读者"
    tone: str = "专业、清晰"
    immediate_publish: bool = False
    image_preference: str = "auto"


@dataclass(slots=True)
class ImageAsset:
    """Represents an image referenced or uploaded by the draft."""

    source_url: str
    alt_text: str
    suggested_name: str = ""
    repo_path: str = ""
    content_type: str = ""
    data: bytes = b""


@dataclass(slots=True)
class AstroArticleDraft:
    """A generated article before repository publishing."""

    title: str
    description: str
    body: str
    slug: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    article_path: str = ""
    rendered_content: str = ""


@dataclass(slots=True)
class ValidationIssue:
    """A human readable validation issue."""

    field: str
    message: str


@dataclass(slots=True)
class ValidationResult:
    """Validation summary for a generated article."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def summary(self) -> str:
        if self.valid:
            return "Astro 预校验通过。"
        return "\n".join(f"- {issue.field}: {issue.message}" for issue in self.issues)


@dataclass(slots=True)
class RepoFileChange:
    """A file that should be written into the target repository."""

    path: str
    content: bytes
    message: str
    encoding: str = "utf-8"


@dataclass(slots=True)
class PublishResult:
    """Outcome of writing the draft to GitHub."""

    mode: str
    branch: str
    commit_sha: str
    article_path: str
    article_title: str
    slug: str
    pr_number: int = 0
    pr_url: str = ""
    article_url: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_lines(self) -> list[str]:
        lines = [
            f"标题: {self.article_title}",
            f"Slug: {self.slug}",
            f"文章路径: {self.article_path}",
            f"写入模式: {self.mode}",
            f"分支: {self.branch}",
            f"Commit: {self.commit_sha}",
        ]
        if self.pr_number:
            lines.append(f"PR 编号: {self.pr_number}")
        if self.pr_url:
            lines.append(f"PR: {self.pr_url}")
        if self.article_url:
            lines.append(f"文章链接: {self.article_url}")
        if self.warnings:
            lines.append("警告: " + "；".join(self.warnings))
        return lines


@dataclass(slots=True)
class PullRequestInfo:
    """A compact representation of a GitHub pull request."""

    number: int
    title: str
    state: str
    url: str
    head: str
    base: str
    merged: bool = False


@dataclass(slots=True)
class PullRequestMergeResult:
    """Outcome of merging a GitHub pull request."""

    number: int
    title: str
    merged: bool
    sha: str
    method: str
    url: str = ""

    def to_lines(self) -> list[str]:
        lines = [
            f"PR 编号: {self.number}",
            f"标题: {self.title}",
            f"合并方式: {self.method}",
            f"状态: {'已合并' if self.merged else '未合并'}",
        ]
        if self.sha:
            lines.append(f"Merge Commit: {self.sha}")
        if self.url:
            lines.append(f"PR: {self.url}")
        return lines


@dataclass(slots=True)
class DeleteResult:
    """Outcome of deleting an article from GitHub."""

    mode: str
    target: str
    deleted_path: str
    branch: str
    commit_sha: str
    pr_number: int = 0
    pr_url: str = ""

    def to_lines(self) -> list[str]:
        lines = [
            f"目标: {self.target}",
            f"已删除: {self.deleted_path}",
            f"写入模式: {self.mode}",
            f"分支: {self.branch}",
            f"Commit: {self.commit_sha}",
        ]
        if self.pr_number:
            lines.append(f"PR 编号: {self.pr_number}")
        if self.pr_url:
            lines.append(f"PR: {self.pr_url}")
        return lines


@dataclass(slots=True)
class ArticleSummary:
    """A lightweight article descriptor used for listing repo content."""

    title: str
    slug: str
    path: str

    def to_line(self) -> str:
        return f"- {self.title} | {self.slug} | {self.path}"


@dataclass(slots=True)
class ScheduledPublishSpec:
    """Placeholder for future scheduled publishing support."""

    cron: str
    prompt: str
    enabled: bool = True


@dataclass(slots=True)
class TaskExecutionResult:
    """Placeholder execution result for future task support."""

    accepted: bool
    message: str
