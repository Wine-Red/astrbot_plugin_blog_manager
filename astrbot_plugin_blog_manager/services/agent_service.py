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

        provider_id = await self.context.get_current_chat_provider_id(event.unified_msg_origin)
        prompt = self._build_prompt(
            request,
            existing_article=existing_article,
            fixed_slug=fixed_slug,
        )
        try:
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
