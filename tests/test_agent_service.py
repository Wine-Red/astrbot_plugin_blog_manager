from astrbot_plugin_blog_manager.models import BlogGenerateRequest
from astrbot_plugin_blog_manager.services.agent_service import AgentService


def test_agent_service_uses_payload_slug_when_available():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(topic="示例文章：欢迎来到我的博客")
    payload = {
        "title": "示例文章：欢迎来到我的博客",
        "slug": "welcome-to-my-blog",
        "description": "desc",
        "body": "# body",
        "tags": ["demo"],
        "images": [],
    }

    draft = service._draft_from_payload(request, payload)

    assert draft.slug == "welcome-to-my-blog"
