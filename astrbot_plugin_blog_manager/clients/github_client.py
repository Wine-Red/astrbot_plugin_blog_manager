"""Minimal async GitHub API client used by the plugin."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from ..exceptions import GitHubClientError
from ..models import PullRequestInfo, PullRequestMergeResult


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
            elif operation.startswith("get_branch_sha:"):
                message = (
                    f"找不到默认分支 `{kwargs_branch_hint(operation)}`。"
                    "请检查 default_branch 是否与 GitHub 仓库中的真实分支名一致。"
                )
            elif operation.startswith("get_pull_request:"):
                message = (
                    f"找不到 PR #{kwargs_pr_hint(operation)}。"
                    "请检查 PR 编号是否正确，或该 PR 是否属于当前仓库。"
                )
            elif operation == "create_pull_request":
                message = (
                    f"创建 PR 失败，可能是目标仓库 `{repo_label}` 不可访问，"
                    "或分支/仓库权限不足。"
                )
            elif operation.startswith("merge_pull_request:"):
                message = (
                    f"无法合并 PR #{kwargs_pr_hint(operation)}。"
                    "请检查 PR 是否存在、是否已关闭，或当前 Token 是否有合并权限。"
                )
            else:
                message = f"GitHub 资源不存在或当前 Token 无权访问：{github_message or response.text}"
        elif response.status_code in (401, 403):
            if operation.startswith("merge_pull_request:"):
                message = (
                    f"合并 PR 权限不足（{response.status_code}）。"
                    "请确认 github_token 具有 Pull requests 写权限，"
                    "并且当前账号对目标仓库拥有合并权限。"
                )
            else:
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

    async def get_file_content(self, path: str, branch: str) -> tuple[str, str]:
        data = await self._request(
            "GET",
            f"{self.repo_api}/contents/{path}",
            params={"ref": branch},
            operation="get_file_content",
        )
        content = str(data.get("content", ""))
        encoding = str(data.get("encoding", "base64"))
        if encoding == "base64":
            decoded = base64.b64decode(content).decode("utf-8")
        else:
            decoded = content
        return decoded, str(data.get("sha", ""))

    async def list_directory(self, path: str, branch: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"{self.repo_api}/contents/{path}",
            params={"ref": branch},
            operation="list_directory",
        )
        if isinstance(data, list):
            return data
        return []

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

    async def delete_file(
        self,
        *,
        path: str,
        message: str,
        branch: str,
        sha: str,
    ) -> dict[str, Any]:
        payload = {
            "message": message,
            "branch": branch,
            "sha": sha,
        }
        return await self._request(
            "DELETE",
            f"{self.repo_api}/contents/{path}",
            json=payload,
            operation="delete_file",
        )

    async def create_pull_request(
        self,
        *,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> PullRequestInfo:
        payload = {"title": title, "head": head, "base": base, "body": body}
        data = await self._request(
            "POST",
            f"{self.repo_api}/pulls",
            json=payload,
            operation="create_pull_request",
        )
        return self._to_pull_request_info(data)

    async def get_pull_request(self, number: int) -> PullRequestInfo:
        data = await self._request(
            "GET",
            f"{self.repo_api}/pulls/{number}",
            operation=f"get_pull_request:{number}",
        )
        return self._to_pull_request_info(data)

    async def merge_pull_request(
        self,
        *,
        number: int,
        method: str = "squash",
        commit_title: str = "",
    ) -> PullRequestMergeResult:
        payload: dict[str, Any] = {"merge_method": method}
        if commit_title:
            payload["commit_title"] = commit_title
        data = await self._request(
            "PUT",
            f"{self.repo_api}/pulls/{number}/merge",
            json=payload,
            operation=f"merge_pull_request:{number}",
        )
        pr_info = await self.get_pull_request(number)
        return PullRequestMergeResult(
            number=number,
            title=pr_info.title,
            merged=bool(data.get("merged", False)),
            sha=str(data.get("sha", "")),
            method=method,
            url=pr_info.url,
        )

    async def verify_repository_access(self, default_branch: str) -> None:
        await self.get_repo()
        await self.get_branch_sha(default_branch)

    def _to_pull_request_info(self, data: dict[str, Any]) -> PullRequestInfo:
        head = data.get("head") or {}
        base = data.get("base") or {}
        return PullRequestInfo(
            number=int(data.get("number", 0)),
            title=str(data.get("title", "")),
            state=str(data.get("state", "")),
            url=str(data.get("html_url", "")),
            head=str((head.get("ref") if isinstance(head, dict) else "") or ""),
            base=str((base.get("ref") if isinstance(base, dict) else "") or ""),
            merged=bool(data.get("merged", False)),
        )


def kwargs_branch_hint(operation: str) -> str:
    prefix = "get_branch_sha:"
    if operation.startswith(prefix):
        return operation[len(prefix) :]
    return "unknown"


def kwargs_pr_hint(operation: str) -> str:
    if ":" in operation:
        return operation.split(":", 1)[1]
    return "unknown"
