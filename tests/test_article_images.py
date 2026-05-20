import asyncio

from astrbot_plugin_blog_manager.models import AstroArticleDraft, BlogGenerateRequest, ImageAsset
from astrbot_plugin_blog_manager.services.agent_service import AgentService
from astrbot_plugin_blog_manager.services.media_service import MediaService


def test_agent_service_prompt_includes_image_requirements():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(
        topic="大模型 Agent 产品趋势",
        image_preference="external",
    )

    prompt = service._build_prompt(request)

    assert "图片要求" in prompt
    assert "图片偏好：external" in prompt
    assert "图片是本次交付的一部分" in prompt
    assert "默认必须给出 1 张" in prompt
    assert "`images` 用作正文配图素材" in prompt
    assert "未找到可靠公开图片来源" in prompt


def test_agent_service_uses_first_image_as_cover_when_cover_missing():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(topic="Astro 图片发布")
    payload = {
        "title": "Astro 图片发布",
        "slug": "astro-image-publish",
        "description": "desc",
        "category": "博客建设",
        "image": "",
        "body": "# body",
        "tags": ["Astro", "图片"],
        "images": [
            {"url": "https://example.com/section.png", "alt": "章节配图"},
        ],
    }

    draft = service._draft_from_payload(request, payload)

    assert draft.frontmatter["image"] == "https://example.com/section.png"
    assert len(draft.images) == 1


def test_agent_service_adds_cover_to_downloadable_images():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(topic="Astro 图片发布")
    payload = {
        "title": "Astro 图片发布",
        "slug": "astro-image-publish",
        "description": "desc",
        "category": "博客建设",
        "image": "https://example.com/cover.png",
        "body": "# body",
        "tags": ["Astro", "图片"],
        "images": [],
    }

    draft = service._draft_from_payload(request, payload)

    assert draft.frontmatter["image"] == "https://example.com/cover.png"
    assert draft.images[0].source_url == "https://example.com/cover.png"
    assert draft.images[0].suggested_name == "cover"


def test_media_service_rewrites_frontmatter_cover_when_downloaded():
    class FakeMediaService(MediaService):
        async def _download_asset(self, asset, draft):
            asset.data = b"image-bytes"
            asset.content_type = "image/png"
            asset.repo_path = self.adapter.build_asset_path(asset, draft)
            return asset

    service = FakeMediaService(
        config={
            "image_mode": "download",
            "asset_dir": "src/assets/blog",
        }
    )
    draft = AstroArticleDraft(
        title="Astro 图片发布",
        description="desc",
        body="![封面图](https://example.com/cover.png)",
        slug="astro-image-publish",
        frontmatter={"image": "https://example.com/cover.png"},
        images=[
            ImageAsset(
                source_url="https://example.com/cover.png",
                alt_text="封面图",
                suggested_name="cover",
            )
        ],
    )

    prepared, changes, warnings = asyncio.run(service.prepare_assets(draft))

    assert not warnings
    assert len(changes) == 1
    assert prepared.frontmatter["image"] == "/src/assets/blog/astro-image-publish/cover.png"
    assert "![封面图](/src/assets/blog/astro-image-publish/cover.png)" in prepared.body
