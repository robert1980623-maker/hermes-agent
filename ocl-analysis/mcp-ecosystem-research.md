# MCP 生态全面调研报告

> 调研时间：2026-05-05
> 调研范围：MCP 协议规范、实现生态、工具链、社区活跃度、与 Hermes Agent Portal-Daemon-CLI 架构的关系

---

## 1. MCP 协议规范

### 1.1 概述

**Model Context Protocol (MCP)** 由 Anthropic 于 2024 年 11 月推出，是一个开放的、基于 JSON-RPC 2.0 的标准化协议，用于 AI 应用（Clients）与外部工具/数据源（Servers）之间的通信。

- **官方仓库**：`modelcontextprotocol/modelcontextprotocol`（8,000+ stars）
- **协议规范**：JSON-RPC 2.0 之上构建
- **最新版本**：`2025-11-25`（已有 5 个版本迭代：2024-11-05 → 2025-03-26 → 2025-06-18 → 2025-11-25 → draft）
- **官方 SDK**：Python `mcp`（v1.27.0，22,878 stars），TypeScript `@modelcontextprotocol/sdk`（v1.29.0，12,341 stars）
- **NPM 月下载量**：~1.36 亿次

### 1.2 核心机制图解

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MCP Client (Host)                          │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────────────────┐ │
│  │ AI Model  │  │ Tool Registry │  │ Sampling Handler (optional)  │ │
│  │ (LLM)     │  │ + Dispatcher │  │ Server→Client LLM requests   │ │ │
│  └─────┬─────┘  └──────┬───────┘  └──────────────┬───────────────┘ │
│        │               │                         │                 │
│        ▼               ▼                         ▼                 │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                    ClientSession                          │     │
│  │  initialize → capabilities exchange → run                │     │
│  └────────────────────┬─────────────────────────────────────┘     │
└───────────────────────┼───────────────────────────────────────────┘
                        │  Transport Layer
          ┌─────────────┼─────────────┐
          │             │             │
     ┌────▼────┐  ┌─────▼─────┐ ┌────▼────┐
     │  Stdio  │  │  HTTP/SSE │ │Streamable│
     │ (stdin/ │  │ (legacy)  │ │   HTTP   │
     │ stdout) │  │           │ │ (modern) │
     └────┬────┘  └─────┬─────┘ └────┬────┘
          │             │             │
┌─────────▼─────────────▼─────────────▼──────────────────────────────┐
│                        MCP Server(s)                                │
│                                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ │
│  │  Tools      │ │  Resources   │ │   Prompts   │ │   Logging    │ │
│  │  list/call  │ │  list/read   │ │   list/get  │ │  setLevel/   │ │
│  │             │ │  subscribe   │ │             │ │  message     │ │
│  └─────────────┘ └──────────────┘ └─────────────┘ └──────────────┘ │
│                                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ │
│  │   Roots     │ │  Sampling    │ │ Completions │ │  Elicitation │ │
│  │  list/      │ │  createMsg   │ │  complete   │ │  create      │ │
│  │  changed    │ │  (server→    │ │  (auto-     │ │  (user input │ │
│  │             │ │   client)    │ │   complete)  │ │   request)   │ │
│  └─────────────┘ └──────────────┘ └─────────────┘ └──────────────┘ │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      Tasks (2025-11-25)                      │  │
│  │  list / get / result / cancel / notifications/tasks/status   │  │
│  │  → 异步/长时间任务的标准化支持                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 1.3 MCP 协议核心方法清单

| 类别 | 方法 | 方向 | 描述 |
|------|------|------|------|
| **初始化** | `initialize` | C→S | 能力协商、版本协商 |
| | `notifications/initialized` | C→S | 初始化完成通知 |
| **工具** | `tools/list` | C→S | 列出可用工具 |
| | `tools/call` | C→S | 调用工具 |
| | `notifications/tools/list_changed` | S→C | 工具列表变更通知 |
| **资源** | `resources/list` | C→S | 列出资源 |
| | `resources/read` | C→S | 读取资源 |
| | `resources/subscribe` | C→S | 订阅资源更新 |
| | `resources/unsubscribe` | C→S | 取消订阅 |
| **Prompts** | `prompts/list` | C→S | 列出提示模板 |
| | `prompts/get` | C→S | 获取提示模板 |
| **Sampling** | `sampling/createMessage` | S→C | 服务器请求 LLM 推理 |
| **Roots** | `roots/list` | S→C | 客户端列出工作区根目录 |
| **Tasks** | `tasks/list/get/result/cancel` | 双向 | 异步长任务管理 |
| **其他** | `ping`, `notifications/cancelled`, `logging/setLevel`, `completion/complete`, `elicitation/create` | | |

### 1.4 传输层演进

| 传输方式 | 状态 | 说明 |
|----------|------|------|
| **Stdio** | ✅ 稳定 | 本地 subprocess，stdin/stdout JSON-RPC |
| **HTTP + SSE** | ⚠️ 已弃用 | 早期 HTTP 传输，SSE 推送 |
| **Streamable HTTP** | ✅ 推荐 | 统一 HTTP 传输，支持 OAuth 2.1 PKCE |

---

## 2. MCP 生态全景

### 2.1 官方 SDK & 工具

| 项目 | Stars | 说明 |
|------|-------|------|
| `modelcontextprotocol/python-sdk` | 22,878 | Python SDK（pip install mcp） |
| `modelcontextprotocol/typescript-sdk` | 12,341 | TypeScript SDK（npm @modelcontextprotocol/sdk） |
| `modelcontextprotocol/servers` | 85,029 | 官方参考服务器集合 |
| `modelcontextprotocol/inspector` | 9,657 | MCP 服务器可视化调试工具 |
| `modelcontextprotocol/registry` | 6,770 | 社区驱动的 MCP 服务器注册表 |
| `modelcontextprotocol/modelcontextprotocol` | 8,002 | 规范 + 文档仓库 |

### 2.2 主流 MCP Server 清单

| 名称 | Stars | 功能 | 维护状态 |
|------|-------|------|----------|
| **punkpeye/awesome-mcp-servers** | 86,226 | MCP 服务器精选合集 | 🔥 活跃 |
| **github/github-mcp-server** | 29,506 | GitHub 官方 MCP 服务器 | 🔥 活跃 |
| **microsoft/playwright-mcp** | 32,010 | 浏览器自动化（Playwright） | 🔥 活跃 |
| **googleapis/mcp-toolbox** | 14,936 | 数据库 MCP 服务器 | 🔥 活跃 |
| **GLips/Figma-Context-MCP** | 14,614 | Figma 设计上下文 | 🔥 活跃 |
| **awslabs/mcp** | 8,949 | AWS 官方 MCP 服务器集合 | 🔥 活跃 |
| **LaurieWired/GhidraMCP** | 8,751 | Ghidra 反汇编集成 | 🔥 活跃 |
| **idosal/git-mcp** | 8,017 | Git 远程 MCP 服务 | 🔥 活跃 |
| **hangwin/mcp-chrome** | 11,375 | Chrome 扩展 MCP | 🔥 活跃 |
| **PrefectHQ/fastmcp** | 24,991 | Pythonic MCP 框架（服务端+客户端） | 🔥 活跃 |
| **activepieces/activepieces** | 22,046 | AI 工作流自动化 (~400 MCP servers) | 🔥 活跃 |
| **casdoor/casdoor** | 13,548 | 身份认证 + MCP 集成 | 🔥 活跃 |
| **BeehiveInnovations/pal-mcp-server** | 11,505 | 多模型代理 MCP | 🔥 活跃 |

### 2.3 官方参考服务器（modelcontextprotocol/servers/src/）

| 服务器 | 功能 |
|--------|------|
| `everything` | 全功能测试服务器 |
| `fetch` | 网页内容获取 |
| `filesystem` | 本地文件系统访问 |
| `git` | Git 仓库操作 |
| `memory` | 向量记忆存储 |
| `sequentialthinking` | 链式思考工具 |
| `time` | 时间/时区查询 |

### 2.4 社区 MCP 服务器生态分类

**基础设施类**：文件系统、Git、数据库（PostgreSQL、SQLite、MySQL）、Docker、Kubernetes

**开发者工具类**：GitHub、GitLab、Jira、Linear、Sentry、Playwright

**云服务类**：AWS (awslabs/mcp)、Google Cloud、Azure、Cloudflare

**AI/ML 类**：Brave Search、Firecrawl、Tavily、Perplexity、LangChain

**企业集成类**：Slack、Notion、Confluence、Salesforce、Stripe

### 2.5 MCP 客户端生态

| 客户端 | 类型 | 说明 |
|--------|------|------|
| **Claude Desktop** | 桌面应用 | Anthropic 官方桌面客户端 |
| **Claude Code** | CLI | Anthropic 官方编码 CLI（月下载 4588 万） |
| **Cursor** | IDE | AI 编码 IDE，原生 MCP 支持 |
| **VS Code + Copilot** | IDE | Microsoft Copilot MCP 集成 |
| **Windsurf** | IDE | Codeium 的 AI IDE |
| **Cline** | VS Code 扩展 | 开源 AI 编码助手 |
| **LangChain** | 框架 | MCP 工具集成 |
| **LlamaIndex** | 框架 | MCP 数据连接器 |
| **Dify** | 平台 | 140K stars，MCP 集成 |
| **FastGPT** | 平台 | 27K stars，知识库平台 |

---

## 3. 工具链与集成方案

### 3.1 Python MCP 框架

| 框架 | Stars | 特点 |
|------|-------|------|
| **mcp (官方)** | 22,878 | 标准 SDK，FastMCP 高层 API |
| **FastMCP (Prefect)** | 24,991 | 更 Pythonic 的 API，装饰器风格 |
| **dedalus-mcp-python** | 154 | 轻量高性能实现 |

### 3.2 TypeScript MCP 框架

| 框架 | 说明 |
|------|------|
| **@modelcontextprotocol/sdk** | 官方 SDK |
| **mcp-use** | 9,887 stars，全栈 MCP 框架 |

### 3.3 部署与运维工具

| 工具 | 说明 |
|------|------|
| **MCP Inspector** | 可视化 MCP 服务器调试工具 |
| **MCP Registry** | 社区注册表服务 |
| **Smithery** | MCP 服务器托管平台 |
| **Glama** | MCP 服务器发现平台 |

### 3.4 安全与认证

- **OAuth 2.1 + PKCE**：Streamable HTTP 传输的标准认证方案
- **环境隔离**：Stdio 服务器通过 subprocess 隔离
- **工具过滤**：客户端侧 include/exclude 白名单/黑名单

---

## 4. 社区活跃度评估

### 4.1 数据概览

| 指标 | 数值 | 时间窗口 |
|------|------|----------|
| MCP Python SDK Stars | 22,878 | 累计 |
| MCP TypeScript SDK Stars | 12,341 | 累计 |
| MCP Servers 仓库 Stars | 85,029 | 累计 |
| Awesome MCP Servers | 86,226 | 累计 |
| MCP NPM 月下载量 | ~1.36 亿 | 最近 30 天 |
| Claude Code NPM 月下载量 | ~4,588 万 | 最近 30 天 |
| GitHub MCP 相关仓库 | 100,516 | 累计搜索结果 |
| MCP 协议版本迭代 | 5 个 | 2024.11 → 2025.11 → draft |

### 4.2 活跃度趋势

- **极高频更新**：MCP Python SDK 最近提交活跃（2026-04-14 仍有更新）
- **协议快速迭代**：约每季度发布一个稳定版本
- **生态爆发增长**：从 2024 年底推出至今，已成为 AI Agent 工具集成的事实标准
- **主流厂商全面支持**：Anthropic、Google、Microsoft、AWS 均有官方实现

### 4.3 风险评估

| 风险 | 级别 | 说明 |
|------|------|------|
| 协议仍在演进 | 🟡 中 | draft 版本持续迭代，API 可能破坏性变更 |
| 生态碎片化 | 🟡 中 | 大量第三方实现，质量参差不齐 |
| 安全漏洞 | 🟡 中 | 新兴协议，安全审计可能不足 |
| 厂商锁定 | 🟢 低 | 开放标准，多家厂商支持 |

---

## 5. 与 Hermes Agent 架构的关系分析

### 5.1 现有架构概览

Hermes Agent 采用的是 **Agent-Gateway-CLI 三层架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                             │
│  ┌───────────┐  ┌──────────────┐  ┌───────────┐            │
│  │   CLI     │  │   Gateway    │  │   ACP     │            │
│  │ (终端TUI)  │  │ (消息平台)   │  │ (IDE集成)  │            │
│  │ Rich +    │  │ Telegram/    │  │ VS Code/  │            │
│  │ prompt_   │  │ Discord/     │  │ Zed/      │            │
│  │ toolkit   │  │ Slack/...    │  │ JetBrains  │            │
│  └─────┬─────┘  └──────┬───────┘  └─────┬─────┘            │
└────────┼───────────────┼────────────────┼──────────────────┘
         │               │                │
         ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent 核心层                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   AIAgent (run_agent.py)               │   │
│  │  • 同步 ReAct 循环                                      │   │
│  │  • OpenAI 格式消息                                      │   │
│  │  • 工具发现 → 调用 → 结果                                │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ ToolRegistry  │  │  ToolSets    │  │   MCP Client     │  │
│  │ (中心化注册)   │  │ (工具分组)    │  │  (mcp_tool.py)   │  │
│  │              │  │              │  │  • Stdio/HTTP    │  │
│  └──────────────┘  └──────────────┘  │  • 动态发现       │  │
│  ┌──────────────┐  ┌──────────────┐  │  • 采样支持       │  │
│  │ Skills Hub   │  │  Memory      │  │  • 工具过滤       │  │
│  │ (技能系统)    │  │ (持久记忆)    │  │  • 2,195 行     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ SessionDB    │  │   Cron       │                        │
│  │ (SQLite FTS5)│  │ (调度器)      │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Hermes 现有的 MCP 集成

Hermes Agent **已经拥有相当完整的 MCP 集成**：

**作为 MCP Client（连接外部 MCP Server）**：
- `tools/mcp_tool.py`（2,195 行）：完整的 MCP 客户端实现
- 支持 Stdio 和 HTTP/StreamableHTTP 传输
- 自动工具发现与注册（`mcp_<server>_<tool>` 命名）
- 动态工具发现（`tools/list_changed` 通知处理）
- Sampling 支持（服务器请求 LLM 推理）
- 工具白名单/黑名单过滤
- OAuth 2.1 PKCE 认证
- 自动重连 + 指数退避
- 每个 MCP 服务器自动创建 toolset

**作为 MCP Server（被外部 MCP Client 连接）**：
- `mcp_serve.py`：暴露 Hermes 消息会话为 MCP 工具
- 10 个工具：conversations_list, messages_read, messages_send, events_poll 等
- 支持 Stdio 传输（HTTP 传输尚不支持）
- 实时事件桥接（轮询 SQLite 数据库）

### 5.3 对比分析：MCP vs Hermes 架构

| 维度 | MCP | Hermes Agent |
|------|-----|--------------|
| **定位** | 工具/数据源连接协议 | 完整的自改进 AI Agent 系统 |
| **范围** | 仅定义 Client-Server 通信 | Agent Loop + 工具 + 技能 + 记忆 + 多平台 |
| **传输** | Stdio, HTTP/SSE, Streamable HTTP | 消息平台 (Telegram 等), CLI TUI, ACP |
| **工具系统** | `tools/list` + `tools/call` | 中心化注册表 + ToolSets + Skills |
| **发现机制** | 初始化时协商能力 | 启动时加载 + `/reload-mcp` + 动态通知 |
| **异步支持** | Tasks API（2025-11-25 新增） | 后台进程管理 + 子代理委派 |
| **记忆** | 无（memory server 示例） | SessionDB (SQLite FTS5) + 用户画像 + Honcho |
| **技能** | 无 | Skills Hub (agentskills.io 标准) |
| **学习循环** | 无 | 自主技能创建 + 自我改进 + 记忆提示 |

### 5.4 集成点分析

#### 已实现（✅）

1. **MCP Client 集成**：Hermes 可以连接任意 MCP Server 并使用其工具
2. **MCP Server 暴露**：Hermes 可作为 MCP Server 被 Claude Code、Cursor 等连接
3. **ACP 适配器**：基于 Agent Client Protocol 的 IDE 集成（VS Code/Zed/JetBrains）
4. **工具注册集成**：MCP 工具自动注册到 Hermes 的 ToolRegistry
5. **ToolSet 集成**：每个 MCP 服务器自动创建 `mcp-<server>` toolset
6. **Sampling 支持**：支持 MCP 服务器发起的 LLM 推理请求
7. **OAuth 2.1**：HTTP MCP 服务器的认证支持

#### 可实现（🔄 待评估）

1. **MCP Server 端 Streamable HTTP**：当前仅支持 Stdio，可添加 HTTP 传输
2. **MCP Prompts 集成**：当前支持 Resource/Prompts utility 工具，可深度整合到 Skills 系统
3. **MCP Roots 支持**：可暴露 Hermes 工作区根目录给 MCP 服务器
4. **MCP Tasks API**：将 Hermes 的后台进程/子代理与 MCP Tasks 映射
5. **MCP Elicitation**：用户输入请求的标准化
6. **MCP Completions**：自动补全建议

#### 不匹配（❌ 不需要）

1. **MCP 作为核心协议替代**：MCP 只是工具连接协议，不替代 Agent Loop、技能系统、记忆系统等核心功能
2. **完全迁移到 MCP**：Hermes 的多平台消息网关（Telegram/Discord/Slack）远超 MCP 的范围

### 5.5 集成可行性评估

| 集成方向 | 可行性 | 复杂度 | 价值 |
|----------|--------|--------|------|
| **增强 MCP Client** | ✅ 已实现 | 低 | 高 — 扩展工具生态 |
| **增强 MCP Server** | 🟡 可行 | 中 | 中 — 允许远程 AI 工具控制 Hermes |
| **MCP → Skills 映射** | 🟡 可行 | 中 | 高 — MCP 工具可被技能系统引用 |
| **MCP Tasks ↔ 子代理** | 🟡 可行 | 中高 | 中 — 标准化异步任务接口 |
| **ACP + MCP 桥接** | 🟡 可行 | 高 | 中 — IDE 中同时使用两种协议 |

---

## 6. 风险点与机会点

### 6.1 风险点

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| **MCP 协议快速迭代** | 需要持续跟进 SDK 更新 | 保持 MCP SDK 版本锁定，定期更新测试 |
| **MCP Server 质量参差** | 不稳定/不安全的第三方服务器 | 已有的 include/exclude 过滤 + 超时控制 |
| **Stdio 进程泄漏** | 僵尸进程占用资源 | 已有自动重连 + 超时 + 清理机制 |
| **工具命名冲突** | MCP 工具与内置工具同名 | 已有 `mcp_<server>_<tool>` 前缀方案 |
| **Secret 泄漏** | 环境变量传递给不信任的 MCP 服务器 | 已有 env 白名单过滤 |

### 6.2 机会点

| 机会 | 价值 | 行动建议 |
|------|------|----------|
| **MCP 作为技能数据源** | 高 | 允许技能声明依赖的 MCP 服务器，自动安装配置 |
| **MCP Server 市场** | 中 | 在 Skills Hub 中增加 MCP 服务器发现和安装 |
| **跨 Agent MCP 协作** | 高 | 多个 Hermes 实例通过 MCP 互相调用工具 |
| **企业 MCP 网关** | 高 | 将 Hermes Gateway 扩展为企业级 MCP 代理网关 |
| **MCP + ACP 融合** | 中 | 在 IDE 中同时暴露 Hermes Agent 能力（ACP）和 MCP 工具 |
| **MCP Server 暴露 Skills** | 高 | 将 Hermes Skills 通过 MCP Server 暴露给外部 AI 工具 |
| **MCP Roots 工作区管理** | 中 | 利用 MCP Roots 标准化多项目工作区上下文 |

---

## 7. 结论与建议

### 7.1 核心结论

1. **Hermes Agent 已经拥有相当成熟的 MCP 集成**，MCP Client 功能完善（2,195 行代码），MCP Server 功能可用（10 个工具）。

2. **MCP 是一个连接协议，不是 Agent 架构**。它解决的是"如何连接外部工具"的问题，而 Hermes 解决的是"如何构建自改进 AI Agent"的问题。两者互补而非竞争。

3. **MCP 生态发展迅猛**，已成为 AI Agent 工具集成的事实标准。保持与 MCP 生态的兼容性对 Hermes 的长期发展至关重要。

### 7.2 建议优先级

**P0 — 立即执行**：
- 持续跟进 MCP SDK 更新（当前 Python v1.27.0，TypeScript v1.29.0）
- 确保 MCP Client 对最新协议版本（2025-11-25）的兼容性
- 完善 MCP Server 的 Streamable HTTP 传输支持

**P1 — 短期规划**：
- 将 MCP Servers 集成到 Skills Hub（发现 → 安装 → 配置 → 启用）
- 增强 MCP Server 功能：暴露 Skills 为 MCP Tools
- 利用 MCP Tasks API 标准化子代理/后台任务接口

**P2 — 中长期**：
- 探索 MCP + ACP 融合方案，统一 IDE 集成体验
- 构建企业级 MCP 代理网关（基于 Hermes Gateway）
- 支持 MCP Roots 标准化工作区上下文
