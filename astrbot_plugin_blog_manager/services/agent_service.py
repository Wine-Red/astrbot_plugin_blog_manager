"""Article generation helpers around AstrBot LLM interfaces."""

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.parse import quote_plus

from ..constants import DEFAULT_AGENT_SYSTEM_PROMPT, FIREFLY_FRONTMATTER_TEMPLATE_TEXT
from ..models import AstroArticleDraft, BlogGenerateRequest, DailyReportRequest, ImageAsset, NewsItem
from ..utils.slug import slugify


class AgentService:
    """Generate article drafts using AstrBot LLM APIs when available."""

    def __init__(self, context: Any, config: Mapping[str, Any]):
        self.context = context
        self.config = config

    async def generate_article(
        self,
        request: BlogGenerateRequest,
        *,
        event: Any | None = None,
        existing_article: str = "",
        fixed_slug: str = "",
    ) -> AstroArticleDraft:
        llm_payload = await self._try_llm_generate(
            request,
            event=event,
            existing_article=existing_article,
            fixed_slug=fixed_slug,
        )
        if llm_payload:
            return self._draft_from_payload(request, llm_payload, fixed_slug=fixed_slug)
        return self._fallback_draft(request)

    async def _try_llm_generate(
        self,
        request: BlogGenerateRequest,
        *,
        event: Any | None = None,
        existing_article: str = "",
        fixed_slug: str = "",
    ) -> dict[str, Any] | None:
        if not event or not hasattr(self.context, "llm_generate"):
            return None
        if not hasattr(self.context, "get_current_chat_provider_id"):
            return None

        prompt = self._build_prompt(
            request,
            existing_article=existing_article,
            fixed_slug=fixed_slug,
        )
        return await self._try_llm_generate_prompt(prompt, event=event)

    async def generate_daily_report(
        self,
        request: DailyReportRequest,
        news_items: list[NewsItem],
        *,
        event: Any | None = None,
        cover_image_url: str = "",
    ) -> AstroArticleDraft:
        """Generate a structured AI daily report draft."""

        prompt = self._build_daily_prompt(request, news_items, cover_image_url=cover_image_url)
        llm_payload = await self._try_llm_generate_prompt(prompt, event=event)
        if llm_payload:
            return self._daily_draft_from_payload(
                request,
                llm_payload,
                news_items,
                cover_image_url=cover_image_url,
            )
        return self._fallback_daily_draft(request, news_items, cover_image_url=cover_image_url)

    async def generate_cover_image(
        self,
        headline: str,
        *,
        event: Any | None = None,
    ) -> str:
        """Generate or build a cover image URL for a daily report."""

        prompt = (
            "Clean editorial cover image for an AI industry daily report, "
            "minimal futuristic newsroom, soft blue and white palette, "
            f"headline theme: {headline}"
        )
        context_url = await self._try_context_image_generation(prompt, event=event)
        if context_url:
            return context_url
        return f"https://image.pollinations.ai/prompt/{quote_plus(prompt)}?width=1200&height=630&nologo=true"

    async def _try_llm_generate_prompt(
        self,
        prompt: str,
        *,
        event: Any | None = None,
    ) -> dict[str, Any] | None:
        if not event or not hasattr(self.context, "llm_generate"):
            return None
        if not hasattr(self.context, "get_current_chat_provider_id"):
            return None

        try:
            provider_id = await self.context.get_current_chat_provider_id(event.unified_msg_origin)
            response = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
        except Exception:
            return None

        completion_text = getattr(response, "completion_text", "")
        return self._parse_json_payload(completion_text)

    async def _try_context_image_generation(self, prompt: str, *, event: Any | None = None) -> str:
        if self.context is None:
            return ""

        for method_name in ("generate_image", "image_generate", "text_to_image", "draw_image"):
            method = getattr(self.context, method_name, None)
            if not callable(method):
                continue
            try:
                try:
                    result = await method(prompt=prompt, event=event)
                except TypeError:
                    result = await method(prompt)
            except Exception:
                continue
            url = self._extract_image_url(result)
            if url:
                return url
        return ""

    def _extract_image_url(self, result: Any) -> str:
        if isinstance(result, str):
            return result.strip()
        if isinstance(result, dict):
            for key in ("url", "image_url", "src"):
                value = str(result.get(key, "")).strip()
                if value:
                    return value
        url = str(getattr(result, "url", "") or getattr(result, "image_url", "")).strip()
        return url

    def _build_prompt(
        self,
        request: BlogGenerateRequest,
        *,
        existing_article: str = "",
        fixed_slug: str = "",
    ) -> str:
        system_prompt = str(
            self.config.get("agent_system_prompt", DEFAULT_AGENT_SYSTEM_PROMPT)
        ).strip()
        prompt = (
            f"{system_prompt}\n\n"
            "请只输出 JSON，不要输出额外解释。JSON 字段必须包含："
            "`title`, `slug`, `description`, `category`, `tags`, `image`, `body`, `images`。\n"
            "`slug` 必须是英文或 ASCII 的 kebab-case 路径片段，例如 `welcome-to-my-blog`，"
            "不要输出中文、空格或下划线。\n"
            "最终发布会使用 Firefly 博客 frontmatter 模板，请围绕下面这套字段组织内容：\n"
            f"{FIREFLY_FRONTMATTER_TEMPLATE_TEXT}\n"
            "`title`、`description`、`category`、`image` 这类字符串内容按可被 YAML 双引号包裹的方式生成，避免换行和未转义引号。\n"
            "`published` 由系统自动写入，不需要你生成。\n"
            "`category` 必须填写一个明确的中文分类，不要留空。\n"
            "`tags` 必须填写 3 到 6 个与主题强相关的中文标签，不要留空，不要只写泛泛词。\n"
            "`image` 必须返回字符串；没有封面图时返回空字符串。\n"
            "`images` 为数组，每个元素包含 `url` 和 `alt`。\n\n"
            f"主题: {request.topic}\n"
            f"补充要求: {request.instructions or '无'}\n"
            f"目标读者: {request.audience}\n"
            f"文风: {request.tone}\n"
            "正文请使用 Markdown/MDX 兼容写法，结构完整，内容充实。"
        )
        if fixed_slug:
            prompt += f"\n必须保留 slug 为：{fixed_slug}"
        if existing_article:
            prompt += f"\n\n以下是当前文章内容，请在此基础上更新，而不是从零重写路径：\n{existing_article}"
        return prompt

    def _build_daily_prompt(
        self,
        request: DailyReportRequest,
        news_items: list[NewsItem],
        *,
        cover_image_url: str = "",
    ) -> str:
        news_text = "\n\n".join(
            item.to_prompt_line(index)
            for index, item in enumerate(news_items, start=1)
        )
        report_date = request.report_date.isoformat()
        return (
            "你是一个严谨的 AI 行业日报编辑。请只输出 JSON，不要输出额外解释。"
            "JSON 字段必须包含：`title`, `description`, `core_keyword`, `body`。\n"
            "你必须基于给定新闻源生成内容，不要编造来源链接。\n"
            "标题必须符合：AI 日报-日期："
            f"{report_date}：<主标题>。\n"
            "description 必须符合：今日 AI 核心速览：<一句话总结>。\n"
            "正文必须严格包含以下结构：\n"
            "1. 开篇语：一段简短、有人情味的今日 AI 趋势总结。\n"
            "2. 新闻列表：每条新闻使用二级或三级标题，必须包含核心摘要、深度解读、来源链接。\n"
            "3. 格式鲜明：多使用 `> ` 引用块、`---` 分割线和 `- ` 列表。\n"
            "核心摘要必须用 Markdown 加粗强调关键公司、技术或数据。\n"
            "来源链接必须使用 Markdown 链接格式。\n"
            "不要生成 frontmatter，不要生成 slug。\n\n"
            f"日报日期：{report_date}\n"
            f"封面图 URL：{cover_image_url or '无'}\n"
            f"额外要求：{request.extra_instructions or '无'}\n\n"
            f"新闻源：\n{news_text}"
        )

    def _parse_json_payload(self, text: str) -> dict[str, Any] | None:
        text = text.strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data

    def _draft_from_payload(
        self,
        request: BlogGenerateRequest,
        payload: dict[str, Any],
        *,
        fixed_slug: str = "",
    ) -> AstroArticleDraft:
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        images_raw = payload.get("images") or []
        images: list[ImageAsset] = []
        if isinstance(images_raw, list):
            for item in images_raw:
                if isinstance(item, dict) and item.get("url"):
                    images.append(
                        ImageAsset(
                            source_url=str(item["url"]),
                            alt_text=str(item.get("alt", request.topic)),
                            suggested_name=str(item.get("alt", request.topic)),
                        )
                    )
        title = str(payload.get("title", "")).strip() or request.topic
        slug = str(payload.get("slug", "")).strip() or fixed_slug
        description = str(payload.get("description", "")).strip() or f"{request.topic} 相关文章"
        category = str(payload.get("category", "")).strip() or "技术"
        image = str(payload.get("image", "")).strip()
        body = str(payload.get("body", "")).strip() or self._fallback_body(request)
        normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        if not normalized_tags:
            normalized_tags = ["AstrBot", "博客", "Astro"]
        return AstroArticleDraft(
            title=title,
            description=description,
            body=body,
            slug=slugify(slug or title),
            frontmatter={"category": category, "image": image},
            tags=normalized_tags,
            images=images,
        )

    def _daily_draft_from_payload(
        self,
        request: DailyReportRequest,
        payload: dict[str, Any],
        news_items: list[NewsItem],
        *,
        cover_image_url: str = "",
    ) -> AstroArticleDraft:
        report_date = request.report_date.isoformat()
        title = str(payload.get("title", "")).strip() or self._daily_title(report_date)
        if not title.startswith("AI 日报-日期："):
            title = self._daily_title(report_date, title)
        description = str(payload.get("description", "")).strip()
        if not description.startswith("今日 AI 核心速览："):
            description = f"今日 AI 核心速览：{description or self._daily_description(news_items)}"
        core_keyword = str(payload.get("core_keyword", "")).strip() or self._core_keyword(news_items)
        body = str(payload.get("body", "")).strip() or self._fallback_daily_body(news_items)
        return AstroArticleDraft(
            title=title,
            description=description,
            body=body,
            slug=f"ai-daily-{report_date}",
            frontmatter={"category": "AI资讯", "image": cover_image_url},
            tags=["AI", "日报", "人工智能", core_keyword],
        )

    def _fallback_daily_draft(
        self,
        request: DailyReportRequest,
        news_items: list[NewsItem],
        *,
        cover_image_url: str = "",
    ) -> AstroArticleDraft:
        report_date = request.report_date.isoformat()
        return AstroArticleDraft(
            title=self._daily_title(report_date),
            description=f"今日 AI 核心速览：{self._daily_description(news_items)}",
            body=self._fallback_daily_body(news_items),
            slug=f"ai-daily-{report_date}",
            frontmatter={"category": "AI资讯", "image": cover_image_url},
            tags=["AI", "日报", "人工智能", self._core_keyword(news_items)],
        )

    def _fallback_draft(self, request: BlogGenerateRequest) -> AstroArticleDraft:
        title = request.topic.strip()
        return AstroArticleDraft(
            title=title,
            description=f"{title} 的整理与分析",
            body=self._fallback_body(request),
            slug=slugify(title),
            frontmatter={"category": "技术", "image": ""},
            tags=["AstrBot", "Astro", "博客"],
        )

    def _fallback_body(self, request: BlogGenerateRequest) -> str:
        return (
            f"# {request.topic}\n\n"
            "## 背景\n\n"
            f"本文围绕“{request.topic}”展开，面向 {request.audience} 进行系统梳理。\n\n"
            "## 核心要点\n\n"
            f"- 结合需求说明：{request.instructions or '围绕主题进行完整展开。'}\n"
            "- 给出清晰的结构化说明、关键概念和实践建议。\n"
            "- 保持 Markdown/MDX 兼容写法，适合直接发布到 Astro 博客。\n\n"
            "## 总结\n\n"
            "将生成链路、前言信息、图片策略和仓库发布能力打通后，AstrBot 就能形成稳定的博客发文闭环。\n"
        )

    def _daily_title(self, report_date: str, headline: str = "今日 AI 核心速览") -> str:
        return f"AI 日报-日期：{report_date}：{headline}"

    def _daily_description(self, news_items: list[NewsItem]) -> str:
        if news_items:
            return f"围绕 {news_items[0].title} 等重点动态，快速梳理产业与技术走向。"
        return "整理今日人工智能行业的重要新闻、技术突破与产业变化。"

    def _core_keyword(self, news_items: list[NewsItem]) -> str:
        text = " ".join(item.title for item in news_items).lower()
        candidates = ["LLM", "Agent", "多模态", "芯片", "开源模型", "生成式AI"]
        for candidate in candidates:
            if candidate.lower() in text:
                return candidate
        return "大模型"

    def _fallback_daily_body(self, news_items: list[NewsItem]) -> str:
        lines = [
            "## 开篇语",
            "",
            "今天的 AI 行业继续沿着模型能力、产品落地和基础设施三条线推进。下面这份日报聚焦值得关注的公开信息，帮助你快速把握今日脉络。",
            "",
            "---",
            "",
            "## 新闻列表",
            "",
        ]
        for index, item in enumerate(news_items, start=1):
            lines.extend(
                [
                    f"### {index}. {item.title}",
                    "",
                    f"> 来源：[{item.source or '原文'}]({item.url})",
                    "",
                    f"- **核心摘要**：{item.summary}",
                    "- **深度解读**：这条动态值得关注，因为它可能影响模型能力演进、产品竞争格局或 AI 基础设施投入节奏。",
                    f"- **来源链接**：[{item.source or item.title}]({item.url})",
                    "",
                    "---",
                    "",
                ]
            )
        if not news_items:
            lines.extend(
                [
                    "### 暂未获取到足够新闻源",
                    "",
                    "- **核心摘要**：搜索服务暂时没有返回可用新闻。",
                    "- **深度解读**：建议检查搜索配置或稍后重试。",
                    "",
                    "---",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"
