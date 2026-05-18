"""Datetime helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(tz=timezone.utc)


def iso_pub_date() -> str:
    """Return an ISO timestamp compatible with Astro frontmatter."""

    return utc_now().isoformat()


def date_path_fragment() -> str:
    """Return a stable date fragment for file naming."""

    return utc_now().strftime("%Y-%m-%d")
