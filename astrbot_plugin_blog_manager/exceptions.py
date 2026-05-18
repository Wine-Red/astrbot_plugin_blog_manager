"""Plugin specific exceptions."""

from __future__ import annotations


class BlogManagerError(Exception):
    """Base exception for predictable plugin failures."""


class PluginConfigError(BlogManagerError):
    """Raised when required plugin configuration is missing or invalid."""


class AstroValidationError(BlogManagerError):
    """Raised when a generated article does not satisfy Astro constraints."""


class GitHubClientError(BlogManagerError):
    """Raised when GitHub API interaction fails."""


class MediaDownloadError(BlogManagerError):
    """Raised when remote media cannot be downloaded or normalized."""


class SearchDisabledError(BlogManagerError):
    """Raised when a search request is attempted while the feature is disabled."""


class TaskFeatureDisabledError(BlogManagerError):
    """Raised when schedule operations are not enabled."""
