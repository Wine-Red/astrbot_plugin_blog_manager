from astrbot_plugin_blog_manager.models import BlogGenerateRequest
from astrbot_plugin_blog_manager.services.agent_service import AgentService


def test_agent_service_build_prompt_requires_richer_article_quality():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(topic="大模型 Agent 产品趋势")

    prompt = service._build_prompt(request)

    assert "不少于 1200 个中文字符" in prompt
    assert "至少 4 个二级标题" in prompt
    assert "Markdown 表格" in prompt
    assert "Markdown 来源链接" in prompt
    assert "不要编造来源" in prompt
    assert "风险与局限" in prompt


def test_agent_service_build_prompt_includes_firefly_writing_guide():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(topic="大模型 Agent 产品趋势")

    prompt = service._build_prompt(request)

    assert "博客写作格式指导" in prompt
    assert "Mermaid 图表" in prompt
    assert "提醒框" in prompt
    assert "不要照抄示例标题、日期、URL" in prompt


def test_agent_service_fallback_body_is_structured():
    service = AgentService(context=None, config={})
    request = BlogGenerateRequest(topic="Astro 博客自动化发布")

    draft = service._fallback_draft(request)

    assert "## 背景与问题定义" in draft.body
    assert "## 核心观点" in draft.body
    assert "## 建议结构" in draft.body
    assert "| 模块 | 写作目标 |" in draft.body
    assert "## 风险与局限" in draft.body
