"""Shared constants for the plugin."""

from __future__ import annotations

PLUGIN_NAME = "astrbot_plugin_blog_manager"

DEFAULT_CONTENT_DIR = "src/content/posts"
DEFAULT_ASSET_DIR = "src/assets/blog"
DEFAULT_ARTICLE_FORMAT = "md"
DEFAULT_WRITE_MODE = "pr"
DEFAULT_IMAGE_MODE = "external"
DEFAULT_BRANCH_PREFIX = "astrbot/blog"
DEFAULT_SITE_BASE_URL = "/"
DEFAULT_REQUIRED_FRONTMATTER_FIELDS = [
    "title",
    "published",
]
DEFAULT_FRONTMATTER_TEMPLATE = {
    "draft": False,
    "comment": True,
    "pinned": False,
    "category": "技术",
    "image": "",
}
DEFAULT_AGENT_SYSTEM_PROMPT = (
    "你是一个严谨的 Astro 博客编辑和技术写作者。你必须生成结构完整、信息密度高、"
    "适合直接发布到 Astro 博客仓库的文章。输出内容要准确、自然、具体，避免空泛套话，"
    "frontmatter 必须与正文一致，并主动补全合适的分类、标签、摘要和可发布的文章结构。"
)
FIREFLY_FRONTMATTER_TEMPLATE_TEXT = """---
title: "你的文章标题"
published: 2026-05-18
description: "这是一段关于文章内容的简短描述，会在首页卡片显示"
image: ""
tags: ["AI", "周报", "科技"]
category: "技术分享"
draft: false
comment: true
pinned: false
---"""
SUPPORTED_ARTICLE_FORMATS = {"md", "mdx"}
SUPPORTED_WRITE_MODES = {"direct", "pr"}
SUPPORTED_IMAGE_MODES = {"external", "download"}
