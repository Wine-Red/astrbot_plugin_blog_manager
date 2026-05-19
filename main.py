from __future__ import annotations

import sys
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# AstrBot 在某些加载方式下不会自动把插件根目录加入 sys.path，
# 这里显式注入一次，确保可以导入同目录下的业务包。
PLUGIN_ROOT = Path(__file__).resolve().parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from astrbot_plugin_blog_manager.constants import PLUGIN_NAME
from astrbot_plugin_blog_manager.exceptions import BlogManagerError
from astrbot_plugin_blog_manager.models import BlogGenerateRequest
from astrbot_plugin_blog_manager.services.blog_service import BlogService
from astrbot_plugin_blog_manager.services.task_service import TaskService
from astrbot_plugin_blog_manager.tools.blog_tools import (
    build_request_from_payload,
    format_delete_summary,
    extract_tool_string,
    format_draft_summary,
    format_help_text,
    format_list_summary,
    format_merge_summary,
    format_publish_summary,
    parse_blog_command,
)


@register(
    PLUGIN_NAME,
    "WineRed",
    "通过 QQ 指令与自然语言管理 GitHub 上的 Astro 博客仓库",
    "1.0.0",
    "https://github.com/Wine-Red/astrbot_plugin_blog_manager",
)
class BlogManagerPlugin(Star):
    """AstrBot plugin entrypoint for Astro blog generation and publishing."""

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        self.blog_service = BlogService(context, self.config)
        self.task_service = TaskService(
            bool(self.config.get("schedule_feature_enabled", False))
        )

    async def initialize(self):
        """Initialize the plugin instance."""

        logger.info("%s initialized", PLUGIN_NAME)

    @filter.command("blog")
    async def blog(self, event: AstrMessageEvent):
        """管理 Astro 博客。支持 publish、draft、daily、list、update、merge、delete、check、config-check。"""

        subcommand, payload = parse_blog_command(event.message_str)
        try:
            if subcommand in ("", "help"):
                yield event.plain_result(format_help_text())
                return
            if subcommand == "config-check":
                yield event.plain_result("\n".join(self.blog_service.config_check()))
                return
            if subcommand == "check":
                if not payload:
                    yield event.plain_result("请在 `/blog check` 后面附带 Markdown 草稿。")
                    return
                yield event.plain_result(
                    "\n".join(self.blog_service.validate_rendered_article(payload))
                )
                return
            if subcommand == "draft":
                request = build_request_from_payload(topic=payload or "未命名文章")
                draft = await self.blog_service.generate_draft(request, event=event)
                yield event.plain_result(format_draft_summary(draft))
                return
            if subcommand == "daily":
                result = await self.blog_service.publish_daily_report(
                    event=event,
                    extra_instructions=payload,
                )
                yield event.plain_result(format_publish_summary(result))
                return
            if subcommand == "list":
                limit = 10
                if payload:
                    try:
                        limit = int(payload)
                    except ValueError:
                        yield event.plain_result("数量必须是整数，例如 `/blog list 10`。")
                        return
                items = await self.blog_service.list_articles(limit=limit)
                yield event.plain_result(format_list_summary(items))
                return
            if subcommand == "update":
                if not payload:
                    yield event.plain_result("请提供文章 slug/路径 和更新要求，例如 `/blog update welcome-to-my-blog 补充一节总结`。")
                    return
                update_parts = payload.split(maxsplit=1)
                if len(update_parts) < 2:
                    yield event.plain_result("请同时提供目标文章和更新要求，例如 `/blog update welcome-to-my-blog 补充一节总结`。")
                    return
                result = await self.blog_service.update_article(
                    target=update_parts[0],
                    instructions=update_parts[1],
                    event=event,
                )
                yield event.plain_result("文章更新完成。\n" + "\n".join(result.to_lines()))
                return
            if subcommand == "merge":
                if not payload:
                    yield event.plain_result("请提供 PR 编号，例如 `/blog merge 12 squash`。")
                    return
                merge_parts = payload.split()
                try:
                    pr_number = int(merge_parts[0])
                except ValueError:
                    yield event.plain_result("PR 编号必须是整数，例如 `/blog merge 12 squash`。")
                    return
                merge_method = merge_parts[1].lower() if len(merge_parts) > 1 else "squash"
                result = await self.blog_service.merge_pull_request(
                    pr_number=pr_number,
                    method=merge_method,
                )
                yield event.plain_result(format_merge_summary(result))
                return
            if subcommand == "delete":
                if not payload:
                    yield event.plain_result("请提供文章 slug 或完整路径，例如 `/blog delete welcome-to-my-blog`。")
                    return
                result = await self.blog_service.delete_article(target=payload)
                yield event.plain_result(format_delete_summary(result))
                return
            if subcommand == "publish":
                request = build_request_from_payload(
                    topic=payload or "未命名文章",
                    immediate_publish=True,
                )
                result = await self.blog_service.publish(request, event=event)
                yield event.plain_result(format_publish_summary(result))
                return
            yield event.plain_result(format_help_text())
        except BlogManagerError as exc:
            yield event.plain_result(f"博客操作失败: {exc}")
        except Exception as exc:  # pragma: no cover - framework edge safety
            logger.exception("Unexpected blog command error: %s", exc)
            yield event.plain_result(f"出现未预期错误: {exc}")

    @filter.llm_tool(name="draft_blog_article")
    async def draft_blog_article(
        self,
        event: AstrMessageEvent,
        topic: str,
        instructions: str = "",
        image_preference: str = "auto",
    ) -> str:
        """生成 Astro 博客文章草稿。

        Args:
            topic(string): 文章主题或标题
            instructions(string): 额外写作要求
            image_preference(string): 图片偏好，可填 auto/external/download
        """

        request = build_request_from_payload(
            topic=extract_tool_string(topic),
            instructions=extract_tool_string(instructions),
            image_preference=extract_tool_string(image_preference, "auto"),
        )
        try:
            draft = await self.blog_service.generate_draft(request, event=event)
            return format_draft_summary(draft)
        except BlogManagerError as exc:
            return f"草稿生成失败: {exc}"

    @filter.llm_tool(name="publish_blog_article")
    async def publish_blog_article(
        self,
        event: AstrMessageEvent,
        topic: str,
        instructions: str = "",
        image_preference: str = "auto",
        immediate_publish: bool = True,
    ) -> str:
        """生成并发布 Astro 博客文章。

        Args:
            topic(string): 文章主题或标题
            instructions(string): 额外写作要求
            image_preference(string): 图片偏好，可填 auto/external/download
            immediate_publish(boolean): 是否立即写入 GitHub 仓库
        """

        if not self.config.get("allow_auto_publish", True):
            return "当前配置未允许通过自然语言工具直接发布。"

        request = BlogGenerateRequest(
            topic=extract_tool_string(topic),
            instructions=extract_tool_string(instructions),
            immediate_publish=bool(immediate_publish),
            image_preference=extract_tool_string(image_preference, "auto"),
        )
        try:
            result = await self.blog_service.publish(request, event=event)
            return format_publish_summary(result)
        except BlogManagerError as exc:
            return f"发布失败: {exc}"

    @filter.llm_tool(name="publish_ai_daily_report")
    async def publish_ai_daily_report(
        self,
        event: AstrMessageEvent,
        instructions: str = "",
    ) -> str:
        """搜索今日 AI 新闻，生成并发布 AI 日报。

        Args:
            instructions(string): 额外日报写作要求
        """

        if not self.config.get("allow_auto_publish", True):
            return "当前配置未允许通过自然语言工具直接发布。"

        try:
            result = await self.blog_service.publish_daily_report(
                event=event,
                extra_instructions=extract_tool_string(instructions),
            )
            return format_publish_summary(result)
        except BlogManagerError as exc:
            return f"AI 日报发布失败: {exc}"

    @filter.llm_tool(name="list_blog_articles")
    async def list_blog_articles(
        self,
        event: AstrMessageEvent,
        limit: int = 10,
    ) -> str:
        """列出博客文章。

        Args:
            limit(number): 返回文章数量，默认 10
        """

        try:
            items = await self.blog_service.list_articles(limit=int(limit))
            return format_list_summary(items)
        except BlogManagerError as exc:
            return f"文章列表获取失败: {exc}"

    @filter.llm_tool(name="update_blog_article")
    async def update_blog_article(
        self,
        event: AstrMessageEvent,
        target: str,
        instructions: str,
    ) -> str:
        """更新博客文章。

        Args:
            target(string): 文章 slug 或完整路径
            instructions(string): 更新要求
        """

        try:
            result = await self.blog_service.update_article(
                target=extract_tool_string(target),
                instructions=extract_tool_string(instructions),
                event=event,
            )
            return "文章更新完成。\n" + "\n".join(result.to_lines())
        except BlogManagerError as exc:
            return f"文章更新失败: {exc}"

    @filter.llm_tool(name="merge_blog_pull_request")
    async def merge_blog_pull_request(
        self,
        event: AstrMessageEvent,
        pr_number: int,
        merge_method: str = "squash",
    ) -> str:
        """合并博客仓库中的 Pull Request。

        Args:
            pr_number(number): 要合并的 PR 编号
            merge_method(string): 合并方式，可填 merge/squash/rebase
        """

        try:
            result = await self.blog_service.merge_pull_request(
                pr_number=int(pr_number),
                method=extract_tool_string(merge_method, "squash") or "squash",
            )
            return format_merge_summary(result)
        except BlogManagerError as exc:
            return f"PR 合并失败: {exc}"

    @filter.llm_tool(name="delete_blog_article")
    async def delete_blog_article(
        self,
        event: AstrMessageEvent,
        target: str,
    ) -> str:
        """删除博客文章。

        Args:
            target(string): 文章 slug 或完整路径
        """

        try:
            result = await self.blog_service.delete_article(target=extract_tool_string(target))
            return format_delete_summary(result)
        except BlogManagerError as exc:
            return f"文章删除失败: {exc}"

    async def terminate(self):
        """Cleanup hook."""

        logger.info("%s terminated", PLUGIN_NAME)
