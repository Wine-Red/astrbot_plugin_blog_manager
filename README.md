# astrbot_plugin_blog_manager

一个基于 AstrBot 的 Astro 博客管理插件，用于通过 QQ 指令或自然语言 Tool 调用来生成、校验并发布文章到 GitHub 上的 Astro 博客仓库。

## 当前能力

- 通过 `/blog draft <主题>` 生成 Astro 兼容文章草稿
- 通过 `/blog publish <主题>` 生成并发布文章到 GitHub
- 通过 `/blog daily [额外要求]` 自动搜索 AI 新闻并发布 AI 日报
- 通过 `/blog check <Markdown>` 做 Astro 预校验
- 通过 `/blog config-check` 检查关键配置
- 支持 AstrBot LLM Tool：
  - `draft_blog_article`
  - `publish_blog_article`
  - `publish_ai_daily_report`
- 支持两种仓库写入模式：
  - `pr`
  - `direct`
- 支持两种图片模式：
  - `external`
  - `download`

## 首期限界

- 首期聚焦“发文闭环”，不是完整的通用仓库管理平台
- 搜索增强与定时日报已预留接口，但尚未实现完整调度闭环
- 当前对 “符合 Astro 校验机制” 的实现方式是插件侧严格预校验
- 若你提供具体博客仓库结构，可继续扩展为真实 schema 校验模式

## 安装

将仓库放入 AstrBot 的插件目录，并确保 `metadata.yaml` 与 `_conf_schema.json` 被正确加载。

## 配置项

在 AstrBot WebUI 中为插件至少配置以下字段：

- `github_token`
- `github_owner`
- `github_repo`
- `default_branch`
- `content_dir`
- `article_format`
- `image_mode`

常见建议：

- `content_dir`: `src/content/blog`
- `asset_dir`: `src/assets/blog`
- `article_format`: `md` 或 `mdx`
- `write_mode`: 首次接入建议使用 `pr`
- `slug`: 文章 slug 会被强制规范为 ASCII kebab-case，不允许中文 slug

## GitHub 权限要求

建议使用具备目标仓库内容写入权限的 PAT Token。若使用 PR 模式，还需要能创建分支和 Pull Request。

## 指令示例

```text
/blog draft 写一篇关于 Astro Content Collections 的实践文章
/blog publish 生成一篇 AI 日报风格的 Astro 文章，强调结构化与可读性
/blog daily 重点关注大模型、Agent 和多模态应用
/blog check ---
title: Demo
description: Demo
pubDate: 2026-01-01T00:00:00+00:00
slug: demo
---

# Demo
Hello Astro
/blog config-check
```

## 自然语言 Tool 示例

当当前会话模型支持 Tool Calling 时，可通过 AstrBot 自然语言触发：

- “帮我生成一篇关于 Astro 博客自动化发布的文章草稿”
- “根据这个主题写一篇文章并直接发布到博客仓库”

插件会通过以下 Tool 暴露能力：

- `draft_blog_article`
- `publish_blog_article`
- `publish_ai_daily_report`

## AI 日报

`/blog daily` 会执行以下流程：

- 使用 AstrBot Context 搜索能力（如存在）或 DuckDuckGo HTML 搜索抓取今日 AI 新闻
- 默认搜索关键词包括 `AI news today`、`人工智能 最新进展`、`LLM breakthroughs`
- 汇总至少 3 条新闻源后，生成符合固定结构的 Markdown 日报
- 优先调用 AstrBot Context 生图能力；若不可用，会生成 Pollinations 封面图 URL
- 使用 Firefly frontmatter：
  - `title`: `AI 日报-日期：<日期>：<主标题>`
  - `description`: `今日 AI 核心速览：<一句话总结>`
  - `tags`: `["AI", "日报", "人工智能", "<当天核心技术词>"]`
  - `category`: `AI资讯`
  - `image`: 封面图 URL

日报 slug 固定为 `ai-daily-YYYY-MM-DD`，保持 ASCII kebab-case，不允许中文 slug。

## Astro 适配说明

当前版本不绑定固定博客仓库结构，而是通过配置实现适配：

- 文章目录由 `content_dir` 控制
- 图片目录由 `asset_dir` 控制
- frontmatter 必填项由 `required_frontmatter_fields` 控制
- 默认 frontmatter 模板由 `default_frontmatter_template` 控制，填写 JSON 或 YAML 文本对象

插件会在发布前执行以下预校验：

- frontmatter 可正常序列化为 YAML
- 必填字段齐全
- `title`、`description`、`pubDate`、`slug` 类型合理
- `slug` 只能包含 ASCII 小写字母、数字和连字符
- 正文非空
- 输出路径位于配置的 `content_dir` 下
- 图片引用与 `image_mode` 一致

## 已知限制

- 未接入真实 Astro 仓库时，无法 100% 复刻目标站点的自定义 schema
- LLM Tool 能力依赖当前会话模型支持函数调用
- `download` 图片模式需要远程图片可访问
- 定时日报与搜索增强目前仅为扩展点

## 开发

推荐先运行测试：

```bash
pytest
```

## 参考

- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
