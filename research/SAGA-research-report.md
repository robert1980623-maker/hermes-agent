# SAGA 项目/模式调研报告

> 调研日期: 2026-05-05
> 目标: 明确 SAGA 定义、分析架构机制、评估对 Hermes Agent (Daemon Agent) 系统的借鉴价值

---

## 一、SAGA 定义澄清：三种主要含义

"SAGA" 在当前技术领域至少指代 **三种完全不同的概念**，需要逐一辨析：

### 1. 分布式事务 SAGA 模式 (Distributed Transaction Pattern)

**来源**: Hector Garcia-Molina & Kenneth Salem, 1987 论文 *"Sagas"*

**定义**: 一种微服务架构中的 **长事务管理模式**，将一个大型分布式事务拆分为一系列本地事务，每个本地事务都有对应的 **补偿操作 (Compensating Transaction)**。

**核心机制**:
```
Transaction:  T1 → T2 → T3 → T4
Compensation:        C3 → C2 → C1   (反向补偿)
```

- **Choreography 编排**: 每个服务发布事件，其他服务监听并触发下一步
- **Orchestration 编排**: 中央协调器 (SAGA Orchestrator) 按顺序指挥各服务

**代表项目**:
- **Apache ServiceComb Saga** (Java) — Alpha + Omega 架构
- **Temporal.io** — 现代工作流引擎，内置 SAGA 模式
- **Camunda Zeebe** — BPMN + SAGA 支持
- **NServiceBus Saga** — .NET 生态

### 2. Graphiti 中的 SagaNode (Temporal Context Graph)

**来源**: Zep Software 的 [Graphiti](https://github.com/getzep/graphiti) 框架

**定义**: 在 Graphiti 的时序上下文图中，**SagaNode 代表一个对话线程/事件序列**，是对一系列 Episodes (原始消息/事件) 的摘要聚合节点。

**核心机制** (从源码确认):
```python
class SagaNode(Node):
    summary: str = ''              # LLM 生成的对话摘要
    first_episode_uuid: str        # 首条消息 ID
    last_episode_uuid: str         # 最后一条消息 ID
    last_summarized_at: datetime   # 上次摘要时间
```

- **Saga 是 Entity 的上层聚合**: Episodes → (LLM 抽取) → Entities/Facts → (归属到) → Sagas
- **自动摘要**: `summarize_sagas.py` 中的 prompt 将多轮对话压缩为事实性知识摘要
- **时序追踪**: 通过 first/last episode UUID 维护对话的时间边界

**图结构关系**:
```
Saga (对话主题)
  ├── has_episode → Episode 1 (消息1)
  ├── has_episode → Episode 2 (消息2)
  └── has_episode → Episode N (消息N)
       ↓ (LLM 抽取)
Entity Nodes + Fact Edges (带时间窗口的事实)
```

### 3. AI Agent 编排中的 SAGA (非主流但有迹可循)

**定义**: 在 Agent 工作流编排领域，部分项目借用 SAGA 概念指代 **多步骤 Agent 任务的编排与补偿机制**，但尚未形成统一标准。

**相关项目**:
- **CrewAI** — 多 Agent 协作流程，支持任务顺序执行和回退
- **LangGraph** — 状态图编排，支持条件边和循环，可实现 SAGA-like 补偿
- **Microsoft AutoGen** — Agent 对话编排，支持多轮协商
- **Temporal.io** — 虽然本质是工作流引擎，但被越来越多用于 Agent 编排

---

## 二、核心机制与架构模式深度分析

### A. 分布式事务 SAGA 模式

#### 架构模式

| 模式 | 描述 | 优缺点 |
|------|------|--------|
| **Choreography (协同式)** | 去中心化，服务间通过事件总线通信 | 简单但调试困难，易形成循环依赖 |
| **Orchestration (编排式)** | 集中式协调器控制流程 | 清晰可控，但协调器成为单点 |

#### 核心机制

1. **补偿事务 (Compensating Transaction)**: 不是技术回滚，而是业务级逆向操作
   - 例: `创建订单` → 补偿: `取消订单`
   - 例: `扣减库存` → 补偿: `恢复库存`

2. **事务状态机**:
   ```
   [STARTED] → [T1_DONE] → [T2_DONE] → ... → [COMPLETED]
                    ↓           ↓
               [COMPENSATING] ← [FAILED_AT_T3]
   ```

3. **重试与幂等**: 每个子事务必须支持幂等执行

#### 适用场景
- 跨多个微服务的业务事务 (电商下单、支付、物流)
- 需要部分成功、部分失败的场景
- 不适合强一致性要求

### B. Graphiti SagaNode 模式

#### 架构设计

```
┌─────────────────────────────────────────┐
│              Graphiti Core               │
│                                          │
│  Episodes (原始输入)                      │
│    ├── message / json / text / fact      │
│    └── 带 metadata 和 timestamp           │
│           ↓                              │
│  LLM Extraction Pipeline                 │
│    ├── Entity Extraction                 │
│    ├── Relationship Extraction           │
│    └── Fact Extraction with validity     │
│           ↓                              │
│  SagaNode (聚合层)                        │
│    ├── summary (LLM 压缩摘要)             │
│    ├── episode range (时间边界)           │
│    └── linked entities (关联实体)         │
│           ↓                              │
│  Temporal Graph Store                    │
│    ├── Neo4j / FalkorDB / Kuzu / Neptune │
│    └── 支持历史查询和时间旅行              │
└─────────────────────────────────────────┘
```

#### 关键设计特点

1. **分层摘要机制**: 不保留所有原始对话，而是用 LLM 生成 Saga 级别的事实摘要
2. **时效性 (Temporality)**: 每个事实都有 `valid_from` 和 `valid_until` 窗口
3. **溯源性 (Provenance)**: 所有知识都追溯到具体 Episode
4. **动态本体 (Learned Ontology)**: 不依赖预定义 schema，从数据中自动学习实体类型

#### 适用场景
- AI Agent 的长期记忆管理
- 跨会话的上下文追踪
- 事实变更历史追踪
- 个性化 Agent 的用户建模

---

## 三、与 Hermes Agent (Daemon Agent) 系统的对比

### Hermes Agent 当前架构概述

| 组件 | 职责 |
|------|------|
| **AIAgent** (`run_agent.py`) | 核心对话循环，LLM 调用 + 工具执行 |
| **Gateway** (`gateway/run.py`) | 多平台消息接入 (Telegram/Discord/Slack 等) |
| **SessionDB** (`hermes_state.py`) | SQLite + FTS5 会话存储 |
| **Memory System** | 多层记忆：对话摘要、用户画像、技能记忆 |
| **Skills** | 程序化记忆，可自动创建和改进 |
| **Subagents** (`delegate_tool.py`) | 并行子 Agent 委托 |
| **Cron** | 定时任务调度 |

### 对比分析

| 维度 | Hermes Agent | 分布式 SAGA | Graphiti SagaNode |
|------|-------------|------------|-------------------|
| **事务性** | 无显式事务保证 | ✅ 核心设计目标 | ❌ 不涉及 |
| **补偿机制** | 无 | ✅ 补偿事务 | ❌ 不涉及 |
| **状态持久化** | SQLite 会话 + 摘要 | 事件溯源 + 状态快照 | 图数据库 + 时间窗口 |
| **长对话管理** | 滑动窗口 + 压缩 | N/A | ✅ Saga 级别摘要 |
| **事实时效性** | 无 | N/A | ✅ valid_from/to |
| **跨会话记忆** | 有限 (FTS5 搜索) | N/A | ✅ 图遍历 + 语义搜索 |
| **Agent 编排** | 简单委托 (subagent) | ✅ 复杂流程编排 | N/A |
| **错误恢复** | 重试 | ✅ 补偿 + 重试 | N/A |

---

## 四、可借鉴的设计模式

### 模式 1: 补偿式任务编排 (来自分布式 SAGA)

**借鉴点**: Hermes 的 subagent 委托目前缺乏失败恢复机制。

**具体设计**:
```
delegate_task("分析数据", "编译报告", "发送邮件")
  ├── Step 1: 分析数据 → ✅ 完成
  ├── Step 2: 编译报告 → ❌ 失败
  │     ↓ 触发补偿
  └── Compensate: 清理分析中间文件
```

**实施方案**:
- 为 `delegate_tool.py` 增加补偿回调参数
- 使用 `hermes_state.py` 记录任务状态机
- 支持声明式任务链:
  ```python
  saga = SagaBuilder()
      .step("analyze", compensate="cleanup")
      .step("compile", compensate="discard_draft")
      .step("send", compensate="recall_email")
      .execute()
  ```

### 模式 2: 时序上下文聚合 (来自 Graphiti SagaNode)

**借鉴点**: Hermes 的会话管理缺少主题级别的聚合和时序追踪。

**具体设计**:
```
Session (跨平台对话流)
  ├── Saga: "项目部署讨论" (Episode 1-15)
  │     ├── Facts: 决定3月15日部署, 改用CockroachDB
  │     ├── Entities: Jordan, Priya, 部署流程
  │     └── Timeline: 2026-05-01 → 2026-05-03
  ├── Saga: "用户偏好配置" (Episode 16-25)
  │     ├── Facts: 喜欢深色模式, 偏好GPT-4
  │     └── Timeline: 2026-05-03 → 2026-05-04
  └── Saga: "技能创建记录" (Episode 26-30)
        └── Facts: 创建了3个新技能
```

**实施方案**:
- 在现有 memory 层增加 Saga 聚合概念
- LLM 定期扫描新对话，自动分组为 Sagas
- 为每个 Saga 维护摘要 + 时间边界 + 关联实体
- 支持 `hermes memory sagas` 命令查看主题历史

### 模式 3: 事件驱动编排 (来自 SAGA Choreography)

**借鉴点**: Hermes 的 cron 和 subagent 可以升级为事件驱动架构。

**具体设计**:
- 引入轻量级事件总线 (内部 pub/sub)
- 工具执行结果作为事件广播
- Cron 任务、Subagent、Memory 更新都作为事件消费者
- 支持事件溯源，所有 Agent 行为可回放

---

## 五、实施建议

### 短期 (可立即实施)

1. **Subagent 补偿机制**: 在 `delegate_tool.py` 中增加 `on_failure` 回调
   - 影响范围: 小 (~100行改动)
   - 收益: 子任务失败时自动清理，避免脏状态

2. **会话主题聚合**: 在 `hermes_state.py` 中增加 Saga-like 元数据层
   - 用 LLM 定期生成会话主题摘要
   - 存储为 session metadata 的新字段
   - 影响范围: 中 (~300行改动)

### 中期 (需架构调整)

3. **事件总线**: 在 Gateway 和 Agent 之间引入内部事件总线
   - 替代部分直接函数调用
   - 支持异步解耦和事件溯源
   - 影响范围: 大

4. **时序记忆增强**: 为现有 memory system 增加时间窗口
   - 事实标注 valid_from / valid_until
   - 支持 "上次提到 X 是什么时候" 查询
   - 影响范围: 中

### 长期 (战略性)

5. **Saga 编排 DSL**: 为复杂多步骤任务提供声明式编排
   - 类似 LangGraph 的状态图，但更轻量
   - 内置补偿和重试语义
   - 影响范围: 大 (新模块)

### 不推荐直接引入

- **完整的分布式 SAGA 框架** (如 Apache ServiceComb Saga): 过度设计，Hermes 是单体/轻量部署
- **直接集成 Graphiti**: 图数据库依赖太重，与现有 SQLite 架构冲突
- **Temporal.io**: 对于当前规模过于复杂，但可作为未来 Agent 编排的参考

---

## 六、总结

| SAGA 概念 | 对 Hermes 的价值 | 推荐度 |
|-----------|-----------------|--------|
| 分布式事务补偿模式 | 子 Agent 失败恢复 | ⭐⭐⭐⭐ |
| Graphiti SagaNode 时序聚合 | 会话主题级记忆 | ⭐⭐⭐⭐ |
| SAGA Choreography 事件驱动 | Gateway 解耦 | ⭐⭐⭐ |
| SAGA Orchestration 编排器 | 复杂任务流 | ⭐⭐⭐ |
| 完整分布式 SAGA 框架 | 过度工程 | ⭐ |

**核心结论**: SAGA 的两种模式对 Hermes 都有借鉴价值——**分布式 SAGA 的补偿机制** 可以增强 subagent 的可靠性，**Graphiti SagaNode 的时序聚合** 可以增强跨会话记忆的主题组织能力。建议从轻量级的补偿回调和会话主题摘要开始，逐步演进。
