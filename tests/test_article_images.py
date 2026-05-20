import asyncio

from astrbot_plugin_blog_manager.models import AstroArticleDraft, BlogGenerateRequest, ImageAsset
from astrbot_plugin_blog_manager.services.agent_service import AgentService
from astrbot_plugin_blog_manager.services.image_generation_service import ImageGenerationService
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
    assert "封面图策略" in prompt
    assert "默认给出 1 到 3 张" in prompt
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


def test_agent_service_keeps_external_images_as_body_images_with_ai_cover():
    service = AgentService(context=None, config={"cover_image_provider": "gitee"})
    request = BlogGenerateRequest(topic="Astro 图片发布")
    payload = {
        "title": "Astro 图片发布",
        "slug": "astro-image-publish",
        "description": "desc",
        "category": "博客建设",
        "image": "https://example.com/cover-like.png",
        "body": "# body",
        "tags": ["Astro", "图片"],
        "images": [
            {"url": "https://example.com/section.png", "alt": "章节配图"},
        ],
    }

    draft = service._draft_from_payload(request, payload)

    assert draft.frontmatter["image"] == ""
    assert [asset.source_url for asset in draft.images] == [
        "https://example.com/cover-like.png",
        "https://example.com/section.png",
    ]


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


def test_image_generation_service_adds_local_cover_asset():
    class FakeImageGenerationService(ImageGenerationService):
        async def _generate_gitee_cover(self, *, api_key, model, prompt):
            assert "Astro 图片发布" in prompt
            return b"generated-image", "image/png"

    service = FakeImageGenerationService(
        config={
            "cover_image_provider": "gitee",
            "gitee_image_api_key": "token",
            "gitee_image_model": "image-model",
            "asset_dir": "src/assets/blog",
        }
    )
    draft = AstroArticleDraft(
        title="Astro 图片发布",
        description="desc",
        body="# body",
        slug="astro-image-publish",
        frontmatter={"category": "博客建设", "image": ""},
    )

    asyncio.run(
        service.ensure_cover_image(
            BlogGenerateRequest(topic="Astro 图片发布"),
            draft,
        )
    )

    assert draft.frontmatter["image"] == "/src/assets/blog/astro-image-publish/cover.png"
    assert draft.images[0].data == b"generated-image"
    assert draft.images[0].repo_path == "src/assets/blog/astro-image-publish/cover.png"


def test_image_generation_service_generates_cover_when_external_body_images_exist():
    class FakeImageGenerationService(ImageGenerationService):
        async def _generate_gitee_cover(self, *, api_key, model, prompt):
            return b"generated-image", "image/png"

    service = FakeImageGenerationService(
        config={
            "cover_image_provider": "gitee",
            "gitee_image_api_key": "token",
            "gitee_image_model": "image-model",
            "asset_dir": "src/assets/blog",
        }
    )
    draft = AstroArticleDraft(
        title="Astro 图片发布",
        description="desc",
        body="![章节配图](https://example.com/section.png)",
        slug="astro-image-publish",
        frontmatter={"category": "博客建设", "image": ""},
        images=[
            ImageAsset(
                source_url="https://example.com/section.png",
                alt_text="章节配图",
                suggested_name="section",
            )
        ],
    )

    asyncio.run(
        service.ensure_cover_image(
            BlogGenerateRequest(topic="Astro 图片发布"),
            draft,
        )
    )

    assert draft.frontmatter["image"] == "/src/assets/blog/astro-image-publish/cover.png"
    assert draft.images[0].repo_path == "src/assets/blog/astro-image-publish/cover.png"
    assert draft.images[1].source_url == "https://example.com/section.png"


def test_media_service_publishes_generated_image_asset_without_download():
    service = MediaService(config={"image_mode": "external"})
    draft = AstroArticleDraft(
        title="Astro 图片发布",
        description="desc",
        body="# body",
        slug="astro-image-publish",
        frontmatter={"image": "/src/assets/blog/astro-image-publish/cover.png"},
        images=[
            ImageAsset(
                source_url="/src/assets/blog/astro-image-publish/cover.png",
                alt_text="封面图",
                suggested_name="cover",
                repo_path="src/assets/blog/astro-image-publish/cover.png",
                content_type="image/png",
                data=b"generated-image",
            )
        ],
    )

    _, changes, warnings = asyncio.run(service.prepare_assets(draft))

    assert warnings == []
    assert len(changes) == 1
    assert changes[0].path == "src/assets/blog/astro-image-publish/cover.png"
    assert changes[0].content == b"generated-image"
