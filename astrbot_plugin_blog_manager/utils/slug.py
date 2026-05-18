"""Helpers for generating stable article slugs."""

from __future__ import annotations

import re
import unicodedata


def slugify(value: str, default: str = "untitled-post") -> str:
    """Create an ASCII slug suitable for Astro content paths."""

    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or default
