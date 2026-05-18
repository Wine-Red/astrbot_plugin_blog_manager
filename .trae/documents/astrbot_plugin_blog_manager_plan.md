# astrbot_plugin_blog_manager 实现计划

## Summary

在当前 AstrBot 插件模板仓库基础上，实现一个以“发文闭环”为首期目标的博客管理插件：

- 支持 QQ 指令触发与自然语言 Tool 调用双入口。
- 根据用户要求生成符合 Astro 内容校验约束的文章草稿。
- 将文章及可选图片写入 GitHub 上的 Astro 博客仓库。
- 支持两种写入模式：直接提交到默认分支，或创建工作分支并发起 PR。
- 为后续“定时日报/自动搜索发布”预留任务编排与内容生成扩展点，但首期不完整落地任务中心。

首期默认采用以下产品与技术决策：

- 鉴权：GitHub PAT Token。
- 仓库适配：先做可配置的 Astro 适配层，而不是绑定某个固定博客仓库结构。
- 图片策略：支持“外链引用”和“下载入仓库”双模式。
- 结果反馈：向 QQ 返回简洁的执行结果摘要，而不是全文回传。

## Current State Analysis

### 已有文件

- `main.py`
  - 当前仅包含 AstrBot hello world 模板插件。
  - 已确认插件类需放在 `main.py` 中，Handler 需定义在插件类中。
- `metadata.yaml`
  - 已填写插件元信息，仓库名已为 `astrbot_plugin_blog_manager`。
- `README.md`
  - 当前仍是模板说明，未描述本插件功能、配置和使用方式。

### 环境与框架事实

- 当前仓库没有任何业务层目录、配置 Schema、依赖声明或测试文件。
- AstrBot 插件支持：
  - `@filter.command(...)` 指令入口。
  - `@filter.llm_tool(...)` 或 `context.add_llm_tools(...)` 暴露 Tool 给 LLM。
  - `context.tool_loop_agent(...)` 执行带工具的 Agent 工作流。
  - `_conf_schema.json` 定义插件配置，并自动映射为插件配置对象。
  - 插件级 KV 存储，以及 `data/plugin_data/{plugin_name}/` 大文件目录。
- AstrBot 主动型 FutureTask 能力存在，但属于实验性能力；本期只做架构预留，不将其作为首发闭环的依赖。

### 需求收敛结果

- 首期最小可上线闭环：发文闭环。
- 写入模式：支持 PR 模式与直推模式，走配置切换。
- 鉴权方式：PAT Token。
- 触发方式：指令 + 自然语言双入口。
- Astro 博客结构：当前未固定，因此必须可配置。
- Astro 约束：文章生成与落库必须以 Astro 校验机制为目标，不能只生成“看起来像 Markdown”的内容。
- 图片：支持外链模式和入库模式。
- 定时日报：本期仅预留架构，不完整落地。

## Proposed Changes

### 1. 重构 `main.py` 为薄入口

**文件：**

- `main.py`

**改动：**

- 保留 AstrBot 插件注册与主插件类。
- 在插件类中只保留：
  - `__init__`
  - `initialize`
  - `terminate`
  - 指令 Handler
  - LLM Tool Handler
- 将具体业务逻辑委托到外部服务层。

**原因：**

- AstrBot 要求 Handler 写在插件类中，但仓库后续功能复杂，不能继续堆在单文件中。
- 保持入口稳定，便于后续扩展更多命令、任务和能力。

**实现方式：**

- 插件类初始化时加载配置、创建服务实例、注册 LLM Tools。
- 命令入口只负责解析参数、调用应用服务、把结果转换为 AstrBot 消息。

### 2. 新增插件配置 Schema

**文件：**

- `_conf_schema.json`

**改动：**

- 新增完整配置定义，至少包含以下配置项：
  - `github_token`
  - `github_owner`
  - `github_repo`
  - `default_branch`
  - `write_mode`：`direct` / `pr`
  - `pr_branch_prefix`
  - `content_dir`
  - `asset_dir`
  - `article_format`：`md` / `mdx`
  - `image_mode`：`external` / `download`
  - `site_base_url`
  - `frontmatter_schema_mode`
  - `required_frontmatter_fields`
  - `default_frontmatter_template`
  - `allow_auto_publish`
  - `agent_system_prompt`
  - `search_enabled`
  - `schedule_feature_enabled`

**原因：**

- 目标博客仓库结构未固定，必须将路径、Frontmatter 和写入策略参数化。
- 后续如果接入不同 Astro 站点，不需要再修改代码。

**实现方式：**

- 用字符串、布尔、对象、列表等字段描述配置。
- 对 GitHub Token 使用隐藏配置。
- 对写入模式、文章格式、图片模式使用 `options` 提供可视化下拉选择。

### 3. 引入分层目录结构

**文件：**

- `astrbot_plugin_blog_manager/__init__.py`
- `astrbot_plugin_blog_manager/models.py`
- `astrbot_plugin_blog_manager/constants.py`
- `astrbot_plugin_blog_manager/exceptions.py`
- `astrbot_plugin_blog_manager/utils/slug.py`
- `astrbot_plugin_blog_manager/utils/markdown.py`
- `astrbot_plugin_blog_manager/utils/datetime_utils.py`

**改动：**

- 新建插件内部包，承载业务模型、常量、异常和通用工具。

**原因：**

- 首期就会涉及“内容请求 -> 文章草稿 -> Astro 校验 -> 仓库变更 -> 执行摘要”多种对象，继续散落在 `main.py` 不可维护。

**实现方式：**

- `models.py` 定义请求和结果数据结构，例如：
  - `BlogGenerateRequest`
  - `AstroArticleDraft`
  - `RepoWritePlan`
  - `PublishResult`
- `exceptions.py` 统一定义可预期错误，例如：
  - 配置缺失
  - Astro 校验失败
  - GitHub API 失败
  - 图片下载失败

### 4. 新增应用服务层

**文件：**

- `astrbot_plugin_blog_manager/services/blog_service.py`
- `astrbot_plugin_blog_manager/services/publish_service.py`
- `astrbot_plugin_blog_manager/services/agent_service.py`
- `astrbot_plugin_blog_manager/services/task_service.py`

**改动：**

- 将功能按“生成内容”“发布内容”“Agent 编排”“任务预留”拆分。

**原因：**

- 需求中既包含仓库管理，也包含文章生成和未来任务；首期虽不完整实现任务，但结构上要能继续长大。

**实现方式：**

- `blog_service.py`
  - 接收用户意图。
  - 生成标准化文章请求。
  - 调用 Agent 生成候选文章。
  - 触发 Astro 适配校验。
- `publish_service.py`
  - 负责将文章和图片变为仓库变更。
  - 调用 GitHub 服务完成 commit / branch / PR。
- `agent_service.py`
  - 封装 `context.llm_generate` / `context.tool_loop_agent`。
  - 统一系统提示词、步骤上限、工具集构造。
- `task_service.py`
  - 本期只定义任务描述对象、调度入口接口和空实现占位。
  - 不在首期真正创建复杂 FutureTask 管理闭环。

### 5. 新增 Astro 适配层与校验层

**文件：**

- `astrbot_plugin_blog_manager/adapters/astro_adapter.py`
- `astrbot_plugin_blog_manager/adapters/frontmatter_adapter.py`
- `astrbot_plugin_blog_manager/validators/astro_validator.py`

**改动：**

- 实现“符合 Astro 校验机制”的中心能力。

**原因：**

- 用户明确要求文章必须符合 Astro 校验机制。
- 由于目标站点结构未固定，必须把“路径规则”“frontmatter 规则”“内容格式规则”抽离为可配置适配层。

**实现方式：**

- `astro_adapter.py`
  - 根据配置决定文章文件路径、图片路径、扩展名、slug 规则、日期规则。
  - 生成最终要写入仓库的相对路径。
- `frontmatter_adapter.py`
  - 根据配置生成 frontmatter。
  - 合并默认模板、用户指定元信息、运行时生成字段。
- `astro_validator.py`
  - 不依赖本地拉起 Astro 项目，但在插件内做严格预校验。
  - 首期至少校验：
    - frontmatter 为合法 YAML；
    - 必填字段齐全；
    - `slug`、`title`、`description`、`pubDate` 等字段类型正确；
    - 文件扩展名与内容能力匹配；
    - 图片引用与图片模式一致；
    - 文章正文非空，避免空壳文章；
    - 输出文件路径位于配置的内容目录下。
  - 校验失败时阻止提交并返回可读错误。

**补充决策：**

- 这里的“符合 Astro 校验机制”在首期以“对 Astro 内容集合常见约束进行强约束预校验”实现。
- 若后续拿到具体博客仓库，可继续增加“远端 schema 镜像配置”或“本地仓库真实校验”模式。

### 6. 新增 GitHub 仓库访问层

**文件：**

- `astrbot_plugin_blog_manager/clients/github_client.py`
- `astrbot_plugin_blog_manager/services/repository_service.py`

**改动：**

- 统一封装 GitHub API 调用。

**原因：**

- 需要同时支持：
  - 获取远端文件存在性；
  - 创建/更新文章文件；
  - 创建工作分支；
  - 提交图片文件；
  - 发起 PR；
  - 返回 commit SHA、分支名、PR 链接。

**实现方式：**

- 首期采用 GitHub HTTP API 客户端封装，不依赖本地 git clone。
- `github_client.py` 负责 HTTP 请求、鉴权头、错误映射、基础资源操作。
- `repository_service.py` 负责业务语义：
  - 确定提交分支；
  - 检查文件是否冲突；
  - 批量写入文章和图片；
  - 按模式选择“直接提交”或“PR”。

**补充决策：**

- 首期优先保证“单篇文章 + 若干图片资源”的原子化发布体验。
- 仓库通用“任意文件修改”能力只做底层预留，不在第一阶段暴露为完整用户功能面。

### 7. 新增图片处理能力

**文件：**

- `astrbot_plugin_blog_manager/services/media_service.py`

**改动：**

- 支持两种图片策略：
  - 外链模式：直接引用远程 URL。
  - 下载入仓模式：拉取图片后上传到目标博客仓库。

**原因：**

- 用户要求图文并茂，同时希望图片策略可配。

**实现方式：**

- 对 Agent 生成结果中的图片候选进行统一归一化。
- 在 `download` 模式下：
  - 下载图片字节流。
  - 判断扩展名与 MIME。
  - 生成仓库内图片路径。
  - 将 Markdown/MDX 中的图片引用改写为仓库相对路径或站点路径。
- 对下载失败设置回退策略：
  - 若允许回退，则改为外链引用并告警。
  - 若不允许回退，则终止发布。

### 8. 新增命令与自然语言 Tool 入口

**文件：**

- `main.py`
- `astrbot_plugin_blog_manager/tools/blog_tools.py`

**改动：**

- 首期暴露一组最小必要入口：
  - `/blog publish <需求>`
  - `/blog draft <需求>`
  - `/blog check <文本或草稿>`
  - `/blog config-check`
- 同时暴露 LLM Tool，使普通对话中模型可调用发文能力。

**原因：**

- 用户要求“QQ 指令 / 自然语言调用工具”双入口。
- 首期需要兼顾可控手工触发和自然语言编排。

**实现方式：**

- 指令入口：
  - 强调可控、可显式调试。
  - 适合验证 GitHub 提交闭环。
- Tool 入口：
  - 提供给 AstrBot 的 Agent 执行器。
  - 参数设计聚焦文章主题、风格、受众、是否立即发布、图片偏好。

### 9. 设计 Agent 工作流

**文件：**

- `astrbot_plugin_blog_manager/services/agent_service.py`
- `astrbot_plugin_blog_manager/tools/blog_tools.py`

**改动：**

- 建立单 Agent + 工具集的首期方案，而不是一步到位多智能体重编排。

**原因：**

- 首期闭环重点在“稳定发文”，不是复杂编排。
- 但需求明确提到后续会扩展搜索与日报，因此内部提示词与工具接口要能演进到多 Agent。

**实现方式：**

- 生成链路：
  - 输入需求
  - 生成文章计划
  - 生成 frontmatter + 正文 + 图片建议
  - 通过 Astro 校验器
  - 通过发布服务提交
- 若 AstrBot 当前会话模型支持工具调用，则优先用 `tool_loop_agent()`。
- 若当前模型或环境不适合工具循环，则回退到普通文本生成 + 插件侧校验发布。

### 10. 为“搜索增强”和“定时日报”预留扩展点

**文件：**

- `astrbot_plugin_blog_manager/services/search_service.py`
- `astrbot_plugin_blog_manager/services/task_service.py`
- `astrbot_plugin_blog_manager/models.py`

**改动：**

- 新建搜索服务和任务服务的接口层与占位实现。

**原因：**

- 用户已明确未来目标包括自动搜索、生成 AI 日报、定时触发与发布。
- 本期若不预留接口，后续会大量返工。

**实现方式：**

- `search_service.py`
  - 首期只提供抽象接口与禁用态处理。
  - 后续可接 AstrBot 内建 web search、外部搜索 API 或 MCP。
- `task_service.py`
  - 定义 `ScheduledPublishSpec`、`TaskExecutionResult` 等结构。
  - 定义 `schedule_daily_report(...)` 之类的方法签名，但首期仅返回“未启用/未实现完整调度”。

### 11. 补全文档与使用说明

**文件：**

- `README.md`

**改动：**

- 将模板 README 改为本插件真实文档，至少包含：
  - 插件定位
  - 支持能力与首期限界
  - 必填配置说明
  - GitHub 权限要求
  - 指令示例
  - 自然语言触发示例
  - PR 模式与直推模式说明
  - Astro 适配配置说明
  - 已知限制

**原因：**

- 首期功能较多，没有 README 无法安装和调试。

### 12. 增加依赖声明与基础测试

**文件：**

- `requirements.txt`
- `tests/test_astro_validator.py`
- `tests/test_slug.py`
- `tests/test_frontmatter_adapter.py`

**改动：**

- 增加最小依赖声明。
- 增加少量高价值单元测试。

**原因：**

- 当前仓库没有依赖文件，也没有测试。
- Astro 预校验、slug、frontmatter 组装是最容易回归出错且最适合单测的区域。

**实现方式：**

- 依赖倾向：
  - HTTP 客户端
  - YAML 解析
  - 数据模型/校验
- 测试只覆盖高价值纯函数和校验器，不为 AstrBot 框架行为写低价值样板测试。

## Assumptions & Decisions

### 已确认决策

- 首期目标不是“通用仓库管理平台”，而是“稳定的 Astro 发文闭环”。
- 首期优先做文章生成、Astro 校验预检、GitHub 提交/PR。
- 定时任务、日报自动化、搜索增强本期只做架构预留。
- 采用 PAT Token。
- 采用指令 + 自然语言双入口。
- 写入模式为可配置双模式。
- 图片模式为可配置双模式。

### 关键实现决策

- 采用“插件侧严格预校验 + GitHub API 发布”的方案，不要求本地存在博客仓库。
- 因目标 Astro 仓库结构未固定，所有关键路径和 frontmatter 约束均配置化。
- 首期把“符合 Astro 校验机制”解释为：
  - 文章输出符合 Astro Content Collections 常见约束；
  - 以可配置 frontmatter 规则进行严格校验；
  - 在缺少真实博客仓库 schema 的情况下，阻止明显不合规内容进入仓库。
- 若未来用户提供具体博客仓库结构，再扩展“真实仓库 schema 校验”或“基于仓库模板自动发现配置”能力。

### 风险与处理

- 风险：没有具体博客仓库，无法做到 100% 与真实 schema 完全一致。
  - 处理：将内容目录、frontmatter 必填字段、默认模板做成配置，并在 README 中明确首期约束。
- 风险：当前会话模型可能不支持 Tool Calling。
  - 处理：保留指令入口；Tool 入口作为增强能力，不作为唯一链路。
- 风险：下载图片再入仓可能引入格式与大小问题。
  - 处理：媒体服务加入 MIME 检查、命名规范和失败回退策略。

## Verification Steps

实现阶段按以下顺序验证：

1. 配置加载验证
   - 插件能被 AstrBot 正常识别与加载。
   - `_conf_schema.json` 可在 WebUI 正常显示并保存配置。

2. 指令入口验证
   - `/blog config-check` 能检查 GitHub 和 Astro 关键配置是否完整。
   - `/blog draft <需求>` 能返回草稿摘要且不写仓库。

3. Astro 校验验证
   - 合法 frontmatter + 正文可通过校验。
   - 缺失必填字段、非法 YAML、空正文、非法路径能被阻止。

4. GitHub 提交验证
   - 直推模式下可创建/更新文章文件并返回 commit 信息。
   - PR 模式下可创建分支、提交文件并返回 PR 链接。

5. 图片模式验证
   - 外链模式下文章中的图片 URL 保持可用。
   - 下载模式下图片可写入仓库并正确改写引用。

6. 自然语言 Tool 验证
   - 在支持 Tool Calling 的模型上，可通过自然语言触发文章生成/发布。

7. 回归测试
   - 单元测试覆盖 slug、frontmatter 组装、Astro 校验器核心逻辑。

## 执行顺序

建议实际实现按以下顺序推进：

1. 重写 `main.py` 为薄入口，建立目录骨架。
2. 增加 `_conf_schema.json` 和基础模型/异常/常量。
3. 实现 `astro_adapter`、`frontmatter_adapter`、`astro_validator`。
4. 实现 GitHub 客户端与发布服务。
5. 实现 blog/publish/agent 服务与首批命令。
6. 暴露 LLM Tool 入口。
7. 补 README、requirements 和测试。
8. 最后补搜索/任务预留接口与禁用态说明。
