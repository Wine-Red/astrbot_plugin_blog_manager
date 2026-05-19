# 项目改进报告

生成时间：2026-05-19

## 本次已完成

### 0. AI 日报自动生成与发布

- 新增 `/blog daily [额外要求]` 指令。
- 新增自然语言 Tool：`publish_ai_daily_report`。
- 新增真实搜索服务：
  - 优先探测 AstrBot Context 中可能存在的 `web_search` / `search_web` / `search` 能力。
  - 若 Context 不提供搜索能力，则回退到 DuckDuckGo HTML 搜索。
  - 默认关键词包括 `AI news today`、`人工智能 最新进展`、`LLM breakthroughs`。
- 日报生成要求至少获取 3 条新闻，否则中止发布。
- 新增日报专用 Prompt，要求正文包含：
  - 开篇语
  - 新闻列表
  - 核心摘要
  - 深度解读
  - Markdown 来源链接
  - 引用块、分割线和列表
- 新增封面图流程：
  - 优先尝试 AstrBot Context 中可能存在的生图接口。
  - 若不可用，则生成 Pollinations 图片 URL 作为封面。
- 日报 Firefly frontmatter 固定为：
  - `title`: `AI 日报-日期：<日期>：<主标题>`
  - `description`: `今日 AI 核心速览：<一句话总结>`
  - `tags`: `["AI", "日报", "人工智能", "<当天核心技术词>"]`
  - `category`: `AI资讯`
  - `image`: 封面图 URL
- 日报 slug 固定为 `ai-daily-YYYY-MM-DD`，不会产生中文 slug。

涉及文件：

- `main.py`
- `astrbot_plugin_blog_manager/models.py`
- `astrbot_plugin_blog_manager/services/search_service.py`
- `astrbot_plugin_blog_manager/services/agent_service.py`
- `astrbot_plugin_blog_manager/services/blog_service.py`
- `astrbot_plugin_blog_manager/tools/blog_tools.py`
- `tests/test_daily_report.py`
- `tests/test_search_service.py`

### 1. 禁止中文 slug

- `slugify()` 已改为只生成 ASCII kebab-case。
- 中文或其他非 ASCII 标题不会再被保留到 slug 中。
- 当输入无法提取 ASCII 片段时，会生成稳定的 `untitled-post-<hash>` 形式，避免空 slug。
- Astro 预校验新增 slug 规则：只允许小写字母、数字和连字符。
- `frontmatter.slug` 如果存在，也会执行同样的 ASCII 校验。

涉及文件：

- `astrbot_plugin_blog_manager/utils/slug.py`
- `astrbot_plugin_blog_manager/validators/astro_validator.py`
- `astrbot_plugin_blog_manager/services/repository_service.py`
- `tests/test_slug.py`
- `tests/test_astro_validator.py`
- `tests/test_agent_service.py`

### 2. 增强仓库路径安全

- 文章写入、更新、删除前会校验路径必须位于 `content_dir` 下。
- 拒绝包含 `..` 的文章路径，避免越界访问仓库其他文件。
- 拒绝非 `.md` / `.mdx` 文章路径。
- `/blog delete` 在 PR 模式下会先解析并校验目标文章，再创建工作分支，减少无效空分支。

涉及文件：

- `astrbot_plugin_blog_manager/services/repository_service.py`
- `tests/test_repository_service.py`

### 3. 增强配置检查

- `/blog config-check` 现在会额外检查枚举配置是否合法：
  - `write_mode`
  - `article_format`
  - `image_mode`
- 仓库写入层会拒绝非法 `write_mode`，避免静默进入异常路径。

涉及文件：

- `astrbot_plugin_blog_manager/services/blog_service.py`
- `astrbot_plugin_blog_manager/services/repository_service.py`

### 4. 修复测试入口稳定性

- 新增 `pytest.ini`，配置 `pythonpath = .`。
- 现在直接运行 `pytest` 可以稳定发现并导入本项目包。

涉及文件：

- `pytest.ini`

### 5. 更新文档

- README 已补充说明：文章 slug 会强制规范为 ASCII kebab-case，不允许中文 slug。
- README 的预校验说明已补充 slug 字符集约束。

涉及文件：

- `README.md`

## 验证结果

已运行：

```bash
pytest
```

结果：

```text
26 passed
```

## 后续建议

### 1. GitHub 写入改为单次 tree commit

当前文章和图片仍是逐个文件通过 Contents API 写入，多个文件会产生多个 commit。建议后续改为 Git tree/commit API，一次提交文章和资源，降低半成功状态。

### 2. 列表与查找支持递归目录

当前 `list/update/delete` 主要扫描 `content_dir` 第一层文件。若 Astro 博客按年份、分类或集合分目录，建议改为 Git Trees API 递归扫描。

### 3. LLM 失败不要静默 fallback

当前 LLM 生成失败时会回退到模板文章。建议在发布动作中默认中止，或至少把 fallback 原因放入发布结果 warning，避免用户误以为模型生成成功。

### 4. 图片下载增加资源限制

建议为 `download` 模式增加最大文件大小、MIME 白名单、重定向限制和同名文件去重，避免下载 HTML、超大文件或覆盖资源。

### 5. 高风险指令增加权限控制

`publish`、`merge`、`delete` 都会改动远程仓库。建议接入 AstrBot 的用户权限或白名单配置，并对删除和合并增加二次确认。
