"""Helpers for generating stable article slugs."""

from __future__ import annotations

import re
import unicodedata


def slugify(value: str, default: str = "untitled-post") -> str:
    """Create a slug suitable for Astro content paths, preserving CJK text."""

    normalized = unicodedata.normalize("NFKC", value).lower().strip()
    normalized = re.sub(r"[\s/_.]+", "-", normalized)

    chars: list[str] = []
    previous_hyphen = False
    for char in normalized:
        if char.isalnum() or _is_cjk(char):
            chars.append(char)
            previous_hyphen = False
            continue
        if not previous_hyphen:
            chars.append("-")
            previous_hyphen = True

    slug = "".join(chars).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or default


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
    )
