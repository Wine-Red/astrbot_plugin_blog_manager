"""Helpers for generating stable ASCII article slugs."""

from __future__ import annotations

import hashlib
import re
import unicodedata


def slugify(value: str, default: str = "untitled-post") -> str:
    """Create an ASCII kebab-case slug suitable for Astro content paths.

    Non-ASCII text is deliberately not preserved. If no ASCII token can be
    derived, a stable short hash is appended to the ASCII-normalized default.
    """

    text = unicodedata.normalize("NFKD", value)
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    normalized = ascii_text.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    slug = re.sub(r"-{2,}", "-", normalized).strip("-")
    if slug:
        return slug

    fallback = re.sub(r"[^a-z0-9]+", "-", default.lower()).strip("-") or "post"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{fallback}-{digest}"
