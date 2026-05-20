"""Cover image generation through OpenAI-compatible image APIs."""

from __future__ import annotations

import base64
from typing import Any, Mapping

import httpx

from ..adapters.astro_adapter import AstroAdapter
from ..models import AstroArticleDraft, BlogGenerateRequest, ImageAsset


class ImageGenerationService:
    """Generate local cover assets when configured."""

    def __init__(self, config: Mapping[str, Any]):
        self.config = config
        self.adapter = AstroAdapter(config)

    async def ensure_cover_image(
        self,
        request: BlogGenerateRequest,
        draft: AstroArticleDraft,
    ) -> None:
        if request.image_preference == "none":
            return
        if str(self.config.get("cover_image_provider", "")).lower() != "gitee":
            return
        if self._has_generated_cover(draft):
            return

        api_key = str(self.config.get("gitee_image_api_key", "")).strip()
        model = str(self.config.get("gitee_image_model", "")).strip()
        if not api_key or not model:
            draft.warnings.append("未生成封面图：缺少 gitee_image_api_key 或 gitee_image_model 配置。")
            return

        try:
            image_bytes, content_type = await self._generate_gitee_cover(
                api_key=api_key,
                model=model,
                prompt=self._build_cover_prompt(request, draft),
            )
        except httpx.HTTPError as exc:
            draft.warnings.append(f"未生成封面图：Gitee 文生图请求失败：{exc}")
            return
        except ValueError as exc:
            draft.warnings.append(f"未生成封面图：{exc}")
            return

        asset = ImageAsset(
            source_url="",
            alt_text=f"{draft.title} 封面图",
            suggested_name="cover",
            content_type=content_type,
            data=image_bytes,
        )
        asset.repo_path = self.adapter.build_asset_path(asset, draft)
        asset.source_url = "/" + asset.repo_path
        draft.frontmatter["image"] = asset.source_url
        draft.images.insert(0, asset)

    def _has_generated_cover(self, draft: AstroArticleDraft) -> bool:
        image = str(draft.frontmatter.get("image", "")).strip()
        if not image:
            return False
        asset_dir = "/" + str(self.config.get("asset_dir", "src/assets/blog")).strip("/") + "/"
        return image.startswith(asset_dir)

    async def _generate_gitee_cover(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
    ) -> tuple[bytes, str]:
        base_url = str(self.config.get("gitee_image_base_url", "https://ai.gitee.com/v1")).rstrip("/")
        size = str(self.config.get("gitee_image_size", "1024x1024")).strip() or "1024x1024"
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url}/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        items = data.get("data")
        if not isinstance(items, list) or not items:
            raise ValueError("Gitee 文生图响应缺少 data。")
        first = items[0]
        if not isinstance(first, dict):
            raise ValueError("Gitee 文生图响应格式不正确。")
        if first.get("b64_json"):
            return base64.b64decode(str(first["b64_json"])), "image/png"
        if first.get("url"):
            return await self._download_generated_url(str(first["url"]))
        raise ValueError("Gitee 文生图响应缺少 b64_json 或 url。")

    async def _download_generated_url(self, url: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content, response.headers.get("content-type", "image/png")

    def _build_cover_prompt(self, request: BlogGenerateRequest, draft: AstroArticleDraft) -> str:
        style = str(
            self.config.get(
                "cover_image_style_prompt",
                "现代中文技术博客封面，信息图风格，清晰主体，干净构图，高对比但不过度炫光，不要文字、水印、logo、二维码。",
            )
        ).strip()
        return (
            f"{style}\n"
            f"文章标题：{draft.title}\n"
            f"文章摘要：{draft.description}\n"
            f"主题：{request.topic}\n"
            "画面应表达文章主题的核心对象和关系，避免通用科技背景、抽象光效和无意义装饰。"
        )
