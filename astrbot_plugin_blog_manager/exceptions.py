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

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        operation: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.operation = operation


class MediaDownloadError(BlogManagerError):
    """Raised when remote media cannot be downloaded or normalized."""

