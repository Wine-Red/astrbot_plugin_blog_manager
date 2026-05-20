# astrbot_plugin_blog_manager

一个基于 AstrBot 的 Astro 博客管理插件，用于通过 QQ 指令或自然语言 Tool 调用来生成、校验并发布文章到 GitHub 上的 Astro 博客仓库。

## 当前能力

- 通过 `/blog draft <主题>` 生成 Astro 兼容文章草稿
- 通过 `/blog publish <主题>` 生成并发布文章到 GitHub
- 通过 `/blog close <PR编号>` 关闭未合并 PR 并尝试删除工作分支
- 通过 `/blog check <Markdown>` 做 Astro 预校验
- 通过 `/blog config-check` 检查关键配置
- 支持 AstrBot LLM Tool：
  - `draft_blog_article`
  - `publish_blog_article`
- 支持两种仓库写入模式：
  - `pr`
  - `direct`
- 支持两种图片模式：
  - `external`
  - `download`

## 首期限界

- 首期聚焦“发文闭环”，不是完整的通用仓库管理平台
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
/blog publish 生成一篇关于大模型 Agent 产品的 Astro 文章，要求 AstrBot 自行搜索并附上新闻来源
/blog close 12
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
- `close_blog_pull_request`

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

## 文章生成流水线

普通文章生成不再只依赖一段提示词。插件会在 LLM 生成草稿后执行结构化流水线：

- 将用户请求规格化为文章类型、来源策略和图片策略
- 从用户输入和正文中抽取 Markdown 来源链接，形成 `SourceRecord`，并标记来源是用户提供还是模型正文生成
- 为可接受来源生成 `EvidenceItem`
- 从 frontmatter、正文和 `images` 字段抽取 `ImageCandidate`
- 拦截明显占位或伪造的来源/图片链接，例如 `example.com`、`localhost`、`.test`
- 默认不信任模型正文里自行生成的“参考/来源/官方”链接，除非配置 `allow_generated_sources=true`
- 默认要求至少 1 张封面或正文配图；如确实不需要图片，可将 `image_preference` 设为 `none`
- 对正文长度、二级标题数量、表格、引用块、图片等给出质量提示

对于新闻、产品、模型、版本、价格、榜单等易变化主题，流水线会要求提供用户输入或工具确认的可核验来源链接；缺少来源时不会发布。

## 写作格式指导

插件会默认读取 `astrbot_plugin_blog_manager/example.md`，并把它作为 Firefly 写作格式指导注入生成提示词。该文件用于约束 frontmatter、slug、Markdown/MDX、数学公式、Mermaid、提醒框、GitHub 仓库卡片和嵌入语法等写作格式。

可选配置：

- `writing_guide_path`: 自定义写作格式指导文件路径；留空时使用插件目录下的 `example.md`
- `writing_guide_max_chars`: 注入提示词的最大字符数，默认 `12000`

模型只会被要求学习格式和语法能力，不应照抄指导文件里的示例标题、日期、URL 或正文。

## Gitee 文生图封面

如果希望稳定获得封面图，可以启用 Gitee AI 文生图。插件会用图像生成接口生成封面，写入仓库的 `asset_dir`，并把 frontmatter `image` 指向本地资源路径；正文配图仍然可以使用 LLM 提供的可靠外链图。

需要配置：

- `cover_image_provider`: `gitee`
- `gitee_image_api_key`: Gitee AI API Key
- `gitee_image_base_url`: 默认 `https://ai.gitee.com/v1`
- `gitee_image_model`: Gitee AI 控制台中可用的图像生成模型 ID
- `gitee_image_size`: 默认 `1024x1024`
- `cover_image_style_prompt`: 封面风格要求

建议使用文生图生成封面，而不是让 LLM 自行挑外链封面。正文配图仍可保留外链，但需要和章节内容强相关，并避免不可访问、热链限制、版权不清或 URL 编造的问题。

## 已知限制

- 未接入真实 Astro 仓库时，无法 100% 复刻目标站点的自定义 schema
- LLM Tool 能力依赖当前会话模型支持函数调用
- `download` 图片模式需要远程图片可访问

## 开发

推荐先运行测试：

```bash
pytest
```

## 参考

- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
