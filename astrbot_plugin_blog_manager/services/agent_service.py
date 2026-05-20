"""Article generation helpers around AstrBot LLM interfaces."""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..constants import DEFAULT_AGENT_SYSTEM_PROMPT, FIREFLY_FRONTMATTER_TEMPLATE_TEXT
from ..models import AstroArticleDraft, BlogGenerateRequest, ImageAsset
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
            "图片要求：\n"
            f"- 图片偏好：{request.image_preference or 'auto'}。\n"
            "- 图片是本次交付的一部分，不是可选装饰；生成文章时必须主动尝试为文章寻找封面图和正文配图。\n"
            "- `image` 用作文章封面。默认必须给出 1 张与主题直接相关、可公开访问、视觉质量稳定的封面 URL。\n"
            "- `images` 用作正文配图素材。默认给出 1 到 3 张，并尽量对应文章中的关键章节、产品、架构、流程或对比对象。\n"
            "- 每张图的 `alt` 必须具体描述图中内容和对应章节，不要只写“配图”“封面图”。\n"
            "- 图片来源优先级：官方产品截图/发布页首图/官方博客配图 > 架构图或文档图 > 论文图表或 GitHub 仓库图片 > 可信媒体图片。\n"
            "- 不要使用与主题无关的通用科技感图库图、纯装饰背景图、模糊抽象图或无法说明信息价值的图片。\n"
            "- 不要编造看似真实但无法访问的图片 URL；图片 URL 必须来自用户提供链接、工具返回结果或你本轮能直接确认的公开页面。\n"
            "- 默认不允许无图交付；如果确实没有可靠图片，不要用假图凑数，返回空图片字段并在正文说明“未找到可靠公开图片来源”，插件会中止发布并提示用户补充图片来源。\n"
            "- 如果 `images` 非空，正文中至少插入 1 张最关键图片，使用标准 Markdown 图片语法，并让 alt 文本可读、可检索。\n\n"
            "文章质量要求：\n"
            "- 默认按“深度分析”写作；如果用户明显要求教程、评测、新闻解读、方案设计或实践复盘，则按对应模式组织。\n"
            "- 正文建议不少于 1200 个中文字符；如果主题很窄，也要给出充分背景、推理过程和可执行建议。\n"
            "- 正文必须有清晰层级：至少 4 个二级标题，每个二级标题下至少 2 段具体内容。\n"
            "- 必须包含：背景与问题定义、核心观点、分章节分析、案例或对比、实践建议、风险与局限、总结。\n"
            "- 至少使用 1 个 Markdown 表格、1 个要点列表和 1 个引用块，提升可读性。\n"
            "- 如果主题涉及新闻、产品、模型、版本、法规、价格、榜单或其他可能变化的信息，必须基于用户提供的来源 URL 或工具返回结果核对事实。\n"
            "- 来源链接只能使用用户在补充要求中提供的 URL、工具返回的 URL，或你本轮能直接确认的公开网页 URL。\n"
            "- 禁止根据公司名、文章标题或记忆自行拼接 URL；禁止使用 example.com、test.com、localhost 等占位链接。\n"
            "- 不要编造来源；如果没有用户提供或工具确认的 URL，不要在正文写 Markdown 来源链接，只能写“缺少已核验来源，以下为待核实分析”，并降低结论确定性。\n"
            "- 来源优先级：官方博客/文档/发布页 > 论文或 GitHub 仓库 > 可信技术媒体 > 聚合站；低质量聚合内容不要作为核心来源。\n"
            "- 避免空泛表达，例如“值得关注”“未来可期”“具有重要意义”；每个判断都要说明原因、影响对象和落地条件。\n"
            "- 不要写成提纲，必须形成可直接发布的完整文章。\n\n"
            f"主题: {request.topic}\n"
            f"补充要求: {request.instructions or '无'}\n"
            f"目标读者: {request.audience}\n"
            f"文风: {request.tone}\n"
            "正文请使用 Markdown/MDX 兼容写法，结构完整，内容充实，段落之间要有自然过渡。"
        )
        if fixed_slug:
            prompt += f"\n必须保留 slug 为：{fixed_slug}"
        if existing_article:
            prompt += f"\n\n以下是当前文章内容，请在此基础上更新，而不是从零重写路径：\n{existing_article}"
        return prompt

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
        image, images = self._normalize_images(image, images, request)
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

    def _normalize_images(
        self,
        cover_image: str,
        images: list[ImageAsset],
        request: BlogGenerateRequest,
    ) -> tuple[str, list[ImageAsset]]:
        normalized: list[ImageAsset] = []
        seen: set[str] = set()
        for asset in images:
            source_url = asset.source_url.strip()
            if not source_url or source_url in seen:
                continue
            seen.add(source_url)
            asset.source_url = source_url
            asset.alt_text = asset.alt_text.strip() or request.topic
            asset.suggested_name = asset.suggested_name.strip() or asset.alt_text
            normalized.append(asset)

        cover_image = cover_image.strip()
        if not cover_image and normalized:
            cover_image = normalized[0].source_url
        if cover_image and cover_image not in seen:
            normalized.insert(
                0,
                ImageAsset(
                    source_url=cover_image,
                    alt_text=f"{request.topic} 封面图",
                    suggested_name="cover",
                ),
            )
        return cover_image, normalized

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
            "> 说明：当前 LLM 生成不可用，以下为插件侧兜底草稿。建议在模型恢复后重新生成，以获得更完整的事实核对、案例和来源链接。\n\n"
            "## 背景与问题定义\n\n"
            f"本文围绕“{request.topic}”展开，面向 {request.audience} 进行系统梳理。"
            "一个可发布的博客文章不应只罗列概念，而应解释问题为什么出现、影响哪些读者、以及读者读完后可以采取什么行动。\n\n"
            f"本次补充要求是：{request.instructions or '围绕主题进行完整展开。'}"
            "后续正式生成时，应把这些要求转化为明确章节、案例、对比和实践建议。\n\n"
            "## 核心观点\n\n"
            "- 文章需要先给出判断，再展开依据，避免只做资料堆叠。\n"
            "- 每个关键结论都应说明原因、适用边界和可能的反例。\n"
            "- 如果涉及新闻、产品、模型版本或价格等会变化的信息，正文应附带 Markdown 来源链接。\n\n"
            "## 建议结构\n\n"
            "| 模块 | 写作目标 |\n"
            "| --- | --- |\n"
            "| 背景 | 解释问题来源和读者为什么需要关心 |\n"
            "| 分析 | 拆解关键机制、案例或对比对象 |\n"
            "| 实践 | 给出可执行步骤、检查清单或决策建议 |\n"
            "| 局限 | 标注不确定性、风险和后续观察点 |\n\n"
            "## 实践建议\n\n"
            "正式文章应优先使用二级标题组织主体内容，并在每个章节下写出完整段落。"
            "如果主题偏技术，应补充实现路径、依赖条件和常见误区；如果主题偏产品，应补充用户场景、竞品对比和可衡量指标。\n\n"
            "## 风险与局限\n\n"
            "兜底草稿无法替代模型生成，也不会主动搜索外部来源。"
            "在发布前，应确认事实是否准确、来源是否充分、frontmatter 摘要是否和正文一致。\n\n"
            "## 总结\n\n"
            "当前草稿提供了可发布文章的骨架。恢复 LLM 后，应重新生成完整正文，让文章具备更高信息密度、更多事实依据和更好的 Markdown 阅读体验。\n"
        )
