"""Minimal async GitHub API client used by the plugin."""

from __future__ import annotations

import base64
import json
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

    async def _request(self, method: str, url: str, *, operation: str = "", **kwargs) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers) as client:
            response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise self._build_error(response, operation=operation)
        if not response.content:
            return {}
        return response.json()

    def _build_error(self, response: httpx.Response, *, operation: str = "") -> GitHubClientError:
        message = response.text
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {}

        github_message = payload.get("message", "").strip() if isinstance(payload, dict) else ""
        repo_label = f"{self.owner}/{self.repo}"

        if response.status_code == 404:
            if operation == "get_repo":
                message = (
                    f"无法访问 GitHub 仓库 `{repo_label}`。"
                    "请检查 github_owner/github_repo 是否填写正确，"
                    "以及 github_token 是否有该仓库的访问权限。私有仓库需要相应授权。"
                )
            elif operation == "get_branch_sha":
                message = (
                    f"找不到默认分支 `{kwargs_branch_hint(operation)}`。"
                    "请检查 default_branch 是否与 GitHub 仓库中的真实分支名一致。"
                )
            elif operation == "create_pull_request":
                message = (
                    f"创建 PR 失败，可能是目标仓库 `{repo_label}` 不可访问，"
                    "或分支/仓库权限不足。"
                )
            else:
                message = f"GitHub 资源不存在或当前 Token 无权访问：{github_message or response.text}"
        elif response.status_code in (401, 403):
            message = (
                f"GitHub 鉴权或权限不足（{response.status_code}）。"
                "请检查 github_token 是否有效，并确认具有仓库 contents/pull requests 权限。"
            )
        else:
            message = f"GitHub API 请求失败 {response.status_code}: {github_message or response.text}"

        return GitHubClientError(
            message,
            status_code=response.status_code,
            operation=operation,
        )

    async def get_repo(self) -> dict[str, Any]:
        return await self._request("GET", self.repo_api, operation="get_repo")

    async def get_branch_sha(self, branch: str) -> str:
        data = await self._request(
            "GET",
            f"{self.repo_api}/git/ref/heads/{branch}",
            operation=f"get_branch_sha:{branch}",
        )
        return data["object"]["sha"]

    async def create_branch(self, branch: str, from_sha: str) -> None:
        payload = {"ref": f"refs/heads/{branch}", "sha": from_sha}
        await self._request(
            "POST",
            f"{self.repo_api}/git/refs",
            json=payload,
            operation="create_branch",
        )

    async def get_file_sha(self, path: str, branch: str) -> str:
        try:
            data = await self._request(
                "GET",
                f"{self.repo_api}/contents/{path}",
                params={"ref": branch},
                operation="get_file_sha",
            )
        except GitHubClientError as exc:
            if exc.status_code == 404:
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
        return await self._request(
            "PUT",
            f"{self.repo_api}/contents/{path}",
            json=payload,
            operation="put_file",
        )

    async def create_pull_request(
        self,
        *,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> str:
        payload = {"title": title, "head": head, "base": base, "body": body}
        data = await self._request(
            "POST",
            f"{self.repo_api}/pulls",
            json=payload,
            operation="create_pull_request",
        )
        return data.get("html_url", "")

    async def verify_repository_access(self, default_branch: str) -> None:
        await self.get_repo()
        await self.get_branch_sha(default_branch)


def kwargs_branch_hint(operation: str) -> str:
    prefix = "get_branch_sha:"
    if operation.startswith(prefix):
        return operation[len(prefix) :]
    return "unknown"
