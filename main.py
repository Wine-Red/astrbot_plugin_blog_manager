from __future__ import annotations

from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.star import Context, Star, register

from astrbot_plugin_blog_manager.constants import PLUGIN_NAME
from astrbot_plugin_blog_manager.exceptions import BlogManagerError
from astrbot_plugin_blog_manager.models import BlogGenerateRequest
from astrbot_plugin_blog_manager.services.blog_service import BlogService
from astrbot_plugin_blog_manager.services.search_service import SearchService
from astrbot_plugin_blog_manager.services.task_service import TaskService
from astrbot_plugin_blog_manager.tools.blog_tools import (
    build_request_from_payload,
    extract_tool_string,
    format_draft_summary,
    format_help_text,
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
        self.search_service = SearchService(bool(self.config.get("search_enabled", False)))
        self.task_service = TaskService(
            bool(self.config.get("schedule_feature_enabled", False))
        )

    async def initialize(self):
        """Initialize the plugin instance."""

        logger.info("%s initialized", PLUGIN_NAME)

    @filter.command("blog")
    async def blog(self, event: AstrMessageEvent):
        """管理 Astro 博客。支持 publish、draft、check、config-check。"""

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
    ) -> MessageEventResult:
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
            yield event.plain_result(format_draft_summary(draft))
        except BlogManagerError as exc:
            yield event.plain_result(f"草稿生成失败: {exc}")

    @filter.llm_tool(name="publish_blog_article")
    async def publish_blog_article(
        self,
        event: AstrMessageEvent,
        topic: str,
        instructions: str = "",
        image_preference: str = "auto",
        immediate_publish: bool = True,
    ) -> MessageEventResult:
        """生成并发布 Astro 博客文章。

        Args:
            topic(string): 文章主题或标题
            instructions(string): 额外写作要求
            image_preference(string): 图片偏好，可填 auto/external/download
            immediate_publish(boolean): 是否立即写入 GitHub 仓库
        """

        if not self.config.get("allow_auto_publish", True):
            yield event.plain_result("当前配置未允许通过自然语言工具直接发布。")
            return

        request = BlogGenerateRequest(
            topic=extract_tool_string(topic),
            instructions=extract_tool_string(instructions),
            immediate_publish=bool(immediate_publish),
            image_preference=extract_tool_string(image_preference, "auto"),
        )
        try:
            result = await self.blog_service.publish(request, event=event)
            yield event.plain_result(format_publish_summary(result))
        except BlogManagerError as exc:
            yield event.plain_result(f"发布失败: {exc}")

    async def terminate(self):
        """Cleanup hook."""

        logger.info("%s terminated", PLUGIN_NAME)
