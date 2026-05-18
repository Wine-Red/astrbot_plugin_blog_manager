"""Markdown helpers."""

from __future__ import annotations

import re
from typing import Iterable

import yaml


FRONTMATTER_BOUNDARY = "---"


def render_markdown_document(frontmatter: dict, body: str) -> str:
    """Render YAML frontmatter followed by the Markdown body."""

    fm_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"{FRONTMATTER_BOUNDARY}\n{fm_text}\n{FRONTMATTER_BOUNDARY}\n\n{body.strip()}\n"


def extract_image_urls(markdown_text: str) -> list[str]:
    """Extract image urls from standard Markdown image syntax."""

    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text)


def append_image_gallery(body: str, images: Iterable[tuple[str, str]]) -> str:
    """Append images to the article body using Markdown syntax."""

    lines = [body.rstrip()]
    for url, alt_text in images:
        lines.append("")
        lines.append(f"![{alt_text}]({url})")
    return "\n".join(lines).strip() + "\n"
