# Hermes Agent x future-agi 集成方案

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Hermes Agent System                            │
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────────┐      │
│  │  CLI /   │    │   Gateway    │    │     Cron Scheduler       │      │
│  │ Telegram │    │  (Multi-Plat)│    │  ┌──────────────────┐    │      │
│  │ Discord  │    │              │    │  │ Patrol Jobs      │    │      │
│  │ Feishu   │    │              │    │  │ Wiki Auto-Grow   │    │      │
│  └────┬─────┘    └──────┬───────┘    │  │ Data Collection  │    │      │
│       │                 │            │  └────────┬─────────┘    │      │
│       │                 │            └───────────┼─────────────┘      │
│       └─────────────────┼────────────────────────┼───────────────────┘
│                         │                        │
│              ┌──────────▼────────────────────────▼──────────────┐      │
│              │              AIAgent / AgentLoop                 │      │
│              │  ┌─────────────┐  ┌────────────┐  ┌───────────┐ │      │
│              │  │Prompt Builder│  │Tool Registry│  │Context Mgr│ │      │
│              │  └──────┬──────┘  └─────┬──────┘  └───────────┘ │      │
│              │         │               │                        │      │
│              │  ┌──────▼───────────────▼──────────────────┐    │      │
│              │  │     hermes_observability middleware      │    │      │
│              │  │  ┌────────────┐ ┌───────────┐ ┌──────┐  │    │      │
│              │  │  │HermesTracer│ │ContentEval│ │ABTest│  │    │      │
│              │  │  └─────┬──────┘ └─────┬─────┘ └──┬───┘  │    │      │
│              │  └────────┼──────────────┼────────────┼─────┘    │      │
│              └───────────┼──────────────┼────────────┼──────────┘      │
│                          │              │            │                 │
└──────────────────────────┼──────────────┼────────────┼─────────────────┘
                           │              │            │
                    OTLP /v1/traces   HTTP API     HTTP API
                           │              │            │
┌──────────────────────────▼──────────────▼────────────▼─────────────────┐
│                        future-agi Platform                              │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │   Tracer (Django) │  │  Model Hub       │  │  Agent Playground    │  │
│  │   ClickHouse DB   │  │  Evals/Datasets  │  │  Graph Execution     │  │
│  │   OTLP Ingestion  │  │  Scoring Engine  │  │  Prompt Optimizer    │  │
│  │   Span Analytics  │  │  Compare Views   │  │  A/B Test Results    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    React Frontend UI                              │  │
│  │  Traces Dashboard │ Eval Results │ A/B Test Stats │ Wiki Quality  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 数据流

```
Hermes Agent                    future-agi
    │                              │
    │── OTLP Spans ──────────────►│  Traces stored in ClickHouse
    │   (agent_run, tool_call,     │  Queryable via GraphQL/REST API
    │    cron_patrol, wiki_eval)   │
    │                              │
    │── Eval Results ────────────►│  Stored as dataset rows
    │   (quality scores,           │  Used for prompt optimization
    │    A/B outcomes)             │
    │                              │
    │◄── Optimized Prompts ◄─────│  Prompt optimizer returns
    │                              │  winning variant configs
    │                              │
```

## 四个场景详解

### 场景 1: Cron Patrol 任务的 Agent 决策追踪

**目标**: 将每次 cron 巡逻任务的 Agent 决策过程记录为完整的 trace，
包含工具调用链、推理过程和最终输出。

**集成点**: `cron/scheduler.py` 的 `run_job()` 函数

**Trace 结构**:
```
hermes.cron_patrol (root span)
├── hermes.tool.web_search
│   ├── hermes.tool.args: {"query": "latest CVE-2026"}
│   └── hermes.tool.duration_ms: 1250
├── hermes.tool.read_file
│   └── hermes.tool.args: {"path": "/tmp/vuln_report.md"}
├── hermes.tool.terminal
│   ├── hermes.tool.args: {"command": "nvd-cli check CVE-2026-xxxx"}
│   └── hermes.tool.result_preview: "CVE confirmed, severity: HIGH"
└── (final_response)
```

### 场景 2: Wiki Auto-Grow 的内容质量评估

**目标**: 自动评估 Agent 生成的 wiki 内容质量，拒绝低质量内容入库。

**集成点**: wiki auto-grow cron job 的后处理阶段

**评估维度**:
| 维度 | 描述 | 阈值 |
|------|------|------|
| accuracy | 事实正确性 | ≥ 0.8 |
| completeness | 主题覆盖度 | ≥ 0.7 |
| clarity | 可读性和结构 | ≥ 0.7 |
| freshness | 信息时效性 | ≥ 0.6 |
| relevance | 与 wiki 范围的对齐 | ≥ 0.8 |

### 场景 3: Agent 工具调用的可视化观测

**目标**: 在 future-agi 中可视化展示 Agent 的工具调用序列、
执行时间、错误率和性能趋势。

**集成点**: `model_tools.py` 的 `handle_function_call()` 包装

**可视化指标**:
- 工具调用频率热力图
- 工具执行时间 P50/P95/P99
- 工具错误率趋势
- 并行 vs 串行工具调用对比
- 各工具的成本分布

### 场景 4: Prompt 优化的 A/B 测试

**目标**: 对比不同 prompt 变体的效果，通过数据驱动优化。

**集成点**: `run_agent.py` 的 prompt 构建阶段

**测试流程**:
```
1. 注册实验: PromptABTester("system-prompt-v3")
2. 添加变体: control, with_rubric, with_examples
3. 流量分配: 加权随机 (50/30/20)
4. 结果收集: score_fn 评估每个输出
5. 统计分析: future-agi 显示胜率、置信区间
6. 决策: 选择胜出变体上线
```

## 配置

```yaml
# ~/.hermes/config.yaml
observability:
  enabled: true
  futureagi_endpoint: "https://app.future-agi.com"
  futureagi_api_key: "${FUTUREAGI_API_KEY}"
  sampling_rate: 1.0  # 1.0 = 100% tracing

  wiki_eval:
    model: "gpt-4o-mini"
    threshold: 0.7
    dimensions:
      accuracy: 0.8
      completeness: 0.7

  ab_tests:
    experiments:
      - id: "system-prompt-v3"
        variants:
          - name: "control"
            weight: 50
          - name: "with_rubric"
            weight: 30
          - name: "with_examples"
            weight: 20
```

## 安装

```bash
# Install OTel SDK (optional, only needed for tracing)
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

# Set environment variables
export HERMES_OBSERVABILITY_ENABLED=1
export FUTUREAGI_OTLP_ENDPOINT=http://localhost:4318
export FUTUREAGI_API_KEY=your_api_key_here
```

## 文件清单

| 文件 | 描述 |
|------|------|
| `hermes_observability/__init__.py` | 包入口 |
| `hermes_observability/tracer.py` | OTel 追踪核心 |
| `hermes_observability/evaluator.py` | Wiki 内容质量评估 |
| `hermes_observability/ab_test.py` | Prompt A/B 测试框架 |
| `hermes_observability/integrations.py` | 集成补丁和辅助函数 |
| `hermes_observability/architecture.md` | 本文档 |
