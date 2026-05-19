"""Article generation helpers around AstrBot LLM interfaces."""

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.parse import quote_plus, urlparse

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
            "你是一个严谨的 AI 行业研究员和日报编辑。请只输出 JSON，不要输出额外解释。"
            "JSON 字段必须包含：`title`, `description`, `core_keyword`, `body`。\n"
            "你必须基于给定新闻源生成内容，不要编造来源链接。\n"
            "标题必须符合：AI 日报-日期："
            f"{report_date}：<主标题>。\n"
            "description 必须符合：今日 AI 核心速览：<一句话总结>。\n"
            "正文必须严格包含以下结构，并且内容必须具体、扎实，禁止空泛总结：\n"
            "1. 开篇语：2 到 3 段，说明今天 AI 行业的主线、冲突点和可能影响。\n"
            "2. 今日数据源概览：列出每个来源、链接、信息类型、可能立场或局限。\n"
            "3. 新闻深度分析：每条新闻使用二级或三级标题，必须包含核心事实、数据源分析、为什么重要、影响对象、后续观察点、来源链接。\n"
            "4. 综合判断：把多条新闻串起来，给出产业、技术和监管三方面判断。\n"
            "5. 格式鲜明：多使用 `> ` 引用块、`---` 分割线和 `- ` 列表。\n"
            "核心事实必须用 Markdown 加粗强调关键公司、技术、时间、数字或裁决结果。\n"
            "来源链接必须使用 Markdown 链接格式。\n"
            "每条新闻的深度分析至少 2 段，不要只写一句“值得关注”。\n"
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
        body = str(payload.get("body", "")).strip() or self._fallback_daily_body(news_items, cover_image_url=cover_image_url)
        body = self._ensure_daily_images(body, news_items, cover_image_url=cover_image_url)
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
            body=self._fallback_daily_body(news_items, cover_image_url=cover_image_url),
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

    def _fallback_daily_body(
        self,
        news_items: list[NewsItem],
        *,
        cover_image_url: str = "",
    ) -> str:
        lines = [
            f"![AI 日报封面]({cover_image_url})" if cover_image_url else "",
            "",
            "## 开篇语",
            "",
            "今天的 AI 行业动态不只是单点新闻的堆叠，而是在基础设施、产业应用、安全治理和资本叙事之间形成相互牵引。下面的日报会逐条拆解搜索工具返回的数据源，重点看事实本身、来源视角，以及它们对行业判断的意义。",
            "",
            "如果一条新闻来自媒体报道，它更适合观察公共叙事和政策/市场关注点；如果来自企业公告或市场资讯，它更适合提取产品、客户、指标和商业动作，但需要警惕营销口径。本文会把这些差异写清楚，而不是只给结论。",
            "",
            "---",
            "",
            "## 今日数据源概览",
            "",
        ]
        for index, item in enumerate(news_items, start=1):
            lines.extend(
                [
                    f"- **来源 {index}**：[{item.source or self._source_label(item.url) or '原文'}]({item.url})",
                    f"  - 标题：{item.title}",
                    f"  - 可用信息：{item.summary}",
                    f"  - 来源解读：{self._source_analysis(item)}",
                ]
            )
        lines.extend(
            [
                "",
                "---",
                "",
                "## 新闻深度分析",
                "",
            ]
        )
        for index, item in enumerate(news_items, start=1):
            illustration = self._news_illustration_url(item)
            lines.extend(
                [
                    f"### {index}. {item.title}",
                    "",
                    f"![{item.title}]({illustration})",
                    "",
                    f"> 来源：[{item.source or self._source_label(item.url) or '原文'}]({item.url})",
                    "",
                    f"- **核心事实**：{item.summary}",
                    f"- **数据源分析**：{self._source_analysis(item)}",
                    "",
                    "这条信息的重要性首先在于它反映了 AI 从模型能力竞争转向真实业务约束的过程。无论是算力、数据、就业、汽车、制造还是安全漏洞，新闻背后都不是单纯的“AI 更强了”，而是组织如何把 AI 嵌入预算、流程、风险控制和产品责任。",
                    "",
                    "进一步看，这类动态通常会影响三类对象：一是企业决策者，他们需要判断 AI 投入是否能形成可衡量回报；二是开发者和产品团队，他们需要把新能力转化为稳定流程；三是监管者和用户，他们关心安全、透明度和责任归属。后续应继续观察是否出现更明确的指标、客户案例、监管动作或技术复现。",
                    "",
                    f"- **来源链接**：[{item.source or item.title}]({item.url})",
                    "",
                    "---",
                    "",
                ]
            )
        lines.extend(
            [
                "## 综合判断",
                "",
                "- **产业侧**：今天的新闻更强调 AI 的落地成本、盈利难题和基础设施转向，说明企业已经从概念验证进入回报核算阶段。",
                "- **技术侧**：大模型、Agent、安全工具和智能制造仍是高频主题，但价值判断越来越依赖真实场景中的稳定性、可解释性和集成成本。",
                "- **治理侧**：诉讼、漏洞披露、监控应用和就业影响共同说明，AI 行业的竞争已经进入法律、伦理和社会接受度共同约束的阶段。",
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

    def _ensure_daily_images(
        self,
        body: str,
        news_items: list[NewsItem],
        *,
        cover_image_url: str = "",
    ) -> str:
        output = body.strip()
        if cover_image_url and cover_image_url not in output:
            output = f"![AI 日报封面]({cover_image_url})\n\n{output}"
        if "![新闻配图" in output:
            return output + "\n"
        gallery: list[str] = ["", "---", "", "## 相关新闻配图", ""]
        for index, item in enumerate(news_items[:5], start=1):
            gallery.extend(
                [
                    f"![新闻配图 {index}：{item.title}]({self._news_illustration_url(item)})",
                    "",
                    f"- 图示主题：{item.title}",
                    f"- 来源：[{item.source or self._source_label(item.url) or '原文'}]({item.url})",
                    "",
                ]
            )
        return output + "\n".join(gallery).rstrip() + "\n"

    def _news_illustration_url(self, item: NewsItem) -> str:
        prompt = (
            "editorial illustration for AI industry news, clean data journalism style, "
            f"topic: {item.title}, source: {item.source or self._source_label(item.url)}"
        )
        return f"https://image.pollinations.ai/prompt/{quote_plus(prompt)}?width=1000&height=560&nologo=true"

    def _source_label(self, url: str) -> str:
        hostname = urlparse(url).netloc.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname

    def _source_analysis(self, item: NewsItem) -> str:
        source = (item.source or self._source_label(item.url)).lower()
        if any(name in source for name in ("cnn", "washingtonpost", "forbes")):
            return "媒体来源，适合观察公共议题、行业叙事和事件影响，但需要结合原始公告或判决文本交叉验证细节。"
        if any(name in source for name in ("ft.com", "markets", "prnewswire", "stocktitan")):
            return "公告或市场资讯来源，适合提取公司动作、产品信息和数字指标，但可能带有企业传播口径。"
        if source == "用户提供":
            return "用户提供的检索摘要，适合快速形成线索，但发布前最好补充原始链接或二次来源。"
        return "公开网页来源，适合提取事件线索；判断重要性时需要关注其发布时间、引用对象和是否提供原始数据。"
