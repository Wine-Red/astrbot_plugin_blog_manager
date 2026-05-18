"""Minimal async GitHub API client used by the plugin."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from ..exceptions import GitHubClientError


class GitHubClient:
    """Wrapper around a subset of the GitHub REST API."""

    def __init__(self, token: str, owner: str, repo: str, timeout: float = 30.0):
        self.owner = owner
        self.repo = repo
        self.timeout = timeout
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "astrbot-plugin-blog-manager",
        }

    @property
    def repo_api(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}"

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers) as client:
            response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise GitHubClientError(
                f"GitHub API 请求失败 {response.status_code}: {response.text}"
            )
        if not response.content:
            return {}
        return response.json()

    async def get_repo(self) -> dict[str, Any]:
        return await self._request("GET", self.repo_api)

    async def get_branch_sha(self, branch: str) -> str:
        data = await self._request("GET", f"{self.repo_api}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    async def create_branch(self, branch: str, from_sha: str) -> None:
        payload = {"ref": f"refs/heads/{branch}", "sha": from_sha}
        await self._request("POST", f"{self.repo_api}/git/refs", json=payload)

    async def get_file_sha(self, path: str, branch: str) -> str:
        try:
            data = await self._request(
                "GET", f"{self.repo_api}/contents/{path}", params={"ref": branch}
            )
        except GitHubClientError as exc:
            if "404" in str(exc):
                return ""
            raise
        return data.get("sha", "")

    async def put_file(
        self,
        *,
        path: str,
        content: bytes,
        message: str,
        branch: str,
        sha: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        return await self._request("PUT", f"{self.repo_api}/contents/{path}", json=payload)

    async def create_pull_request(
        self,
        *,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> str:
        payload = {"title": title, "head": head, "base": base, "body": body}
        data = await self._request("POST", f"{self.repo_api}/pulls", json=payload)
        return data.get("html_url", "")
