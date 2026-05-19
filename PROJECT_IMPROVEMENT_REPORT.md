# 项目改进报告

生成时间：2026-05-19

## 本次已完成

### 0. 简化内容生成边界

- 移除独立新闻工作流，不再维护插件侧新闻搜索、新闻筛选、固定模板和专用发布入口。
- 内容主题、搜索范围、来源引用和 Markdown 风格改由 AstrBot/LLM 根据普通 `/blog publish` 或 `publish_blog_article` 提示词完成。
- 插件侧继续聚焦确定性工程能力：草稿生成、frontmatter、slug、Astro 预校验、图片模式、GitHub 写入和 PR 管理。

涉及文件：

- `main.py`
- `astrbot_plugin_blog_manager/models.py`
- `astrbot_plugin_blog_manager/services/agent_service.py`
- `astrbot_plugin_blog_manager/services/blog_service.py`
- `astrbot_plugin_blog_manager/tools/blog_tools.py`

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
25 passed
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
