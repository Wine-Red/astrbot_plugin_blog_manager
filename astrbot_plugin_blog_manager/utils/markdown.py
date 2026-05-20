"""Markdown helpers."""

from __future__ import annotations

import re
from typing import Any, Iterable

import yaml


FRONTMATTER_BOUNDARY = "---"


def render_markdown_document(frontmatter: dict, body: str) -> str:
    """Render YAML frontmatter followed by the Markdown body."""

    fm_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"{FRONTMATTER_BOUNDARY}\n{fm_text}\n{FRONTMATTER_BOUNDARY}\n\n{body.strip()}\n"


def parse_frontmatter(markdown_text: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a Markdown document."""

    if not markdown_text.startswith(f"{FRONTMATTER_BOUNDARY}\n"):
        return {}
    parts = markdown_text.split(FRONTMATTER_BOUNDARY, 2)
    if len(parts) < 3:
        return {}
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    if isinstance(metadata, dict):
        return metadata
    return {}


def extract_image_urls(markdown_text: str) -> list[str]:
    """Extract image urls from standard Markdown image syntax."""

    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text)


def extract_markdown_links(markdown_text: str) -> list[tuple[str, str]]:
    """Extract non-image Markdown links as ``(label, url)`` tuples."""

    matches = re.finditer(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", markdown_text)
    return [(match.group(1).strip(), match.group(2).strip()) for match in matches]


def extract_urls(markdown_text: str) -> list[str]:
    """Extract bare HTTP(S) URLs from Markdown text."""

    return [
        match.group(0).rstrip(".,;，。；)")
        for match in re.finditer(r"https?://[^\s<>\]]+", markdown_text)
    ]


def append_image_gallery(body: str, images: Iterable[tuple[str, str]]) -> str:
    """Append images to the article body using Markdown syntax."""

    lines = [body.rstrip()]
    for url, alt_text in images:
        lines.append("")
        lines.append(f"![{alt_text}]({url})")
    return "\n".join(lines).strip() + "\n"
