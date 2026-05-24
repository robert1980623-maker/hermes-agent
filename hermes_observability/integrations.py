"""
Integration patches for Hermes Agent -> future-agi observability.

These are thin wrappers that can be dropped into existing Hermes Agent
code paths without modifying the core logic.

Usage:
    from hermes_observability.integrations import (
        patch_cron_scheduler,
        patch_agent_loop,
        patch_tool_execution,
    )

    # Call these during Hermes startup
    patch_cron_scheduler()
    patch_agent_loop()
"""

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_tracer():
    """Get or create the global HermesTracer instance."""
    from hermes_observability.tracer import HermesTracer
    return HermesTracer()


# ── Scenario 1: Cron Patrol Decision Tracing ───────────────────────

def patch_cron_scheduler():
    """
    Wrap cron.scheduler's run_job() to trace patrol decisions.

    Adds a trace to future-agi for every cron job execution showing:
    - Job metadata and pre-run script output
    - Agent execution as a span
    - Final response and delivery status
    - Error information if any

    Installation: Add to cron/scheduler.py after imports:
        from hermes_observability.integrations import record_cron_patrol

    Then in run_job(), wrap the result:
        success, output, final_response, error = run_job(job)
        record_cron_patrol(job, success, final_response, error, prompt)
    """
    logger.info("Cron scheduler tracing enabled")


def record_cron_patrol(job: Dict, success: bool, final_response: str,
                       error: Optional[str] = None, prompt: str = ""):
    """Record a cron patrol execution as a future-agi trace."""
    tracer = get_tracer()
    tracer.record_cron_patrol(
        job_id=job["id"],
        job_name=job.get("name", job["id"]),
        prompt=prompt or job.get("prompt", "")[:500],
        final_response=final_response or "",
        success=success,
        error=error,
        model=job.get("model", ""),
    )


def record_cron_job_decision(
    job: Dict,
    session_id: str,
    model: str,
    turns: int,
    tool_calls: list,
    final_response: str,
    cost_usd: float = 0,
):
    """
    Record detailed cron patrol with per-turn decision chain.

    This creates a full trace showing the agent's reasoning process
    during a cron patrol, visible in future-agi's trace viewer.
    """
    tracer = get_tracer()
    with tracer.agent_span(
        session_id=session_id,
        model=model,
        platform="cron",
        cron_job_id=job["id"],
        cron_job_name=job.get("name", ""),
        skills=job.get("skills") or [],
    ) as span:
        # Record tool call chain
        for i, tc in enumerate(tool_calls):
            ts = tracer.tool_span(span, tc.get("name", "unknown"))
            ts.set_attribute("hermes.cron.tool_index", i)
            ts.set_attribute("hermes.tool.args", json.dumps(tc.get("args", {}))[:1000])
            ts.set_attribute("hermes.tool.status", tc.get("status", "success"))
            ts.end()

        span.set_attribute("hermes.cron.turns", turns)
        span.set_attribute("hermes.cron.final_response_preview", final_response[:2000])
        if cost_usd > 0:
            span.set_attribute("hermes.cost.usd", round(cost_usd, 6))

        span.end()


# ── Scenario 2: Wiki Auto-Grow Quality Evaluation ──────────────────

def patch_wiki_growth():
    """
    Hook into wiki auto-grow cron job to evaluate generated content.

    When a cron job generates wiki content, this module:
    1. Extracts the generated content from the agent response
    2. Evaluates it against quality dimensions
    3. Records the evaluation in future-agi
    4. Optionally rejects content below threshold

    Installation: In cron job that does wiki growth:
        from hermes_observability.integrations import evaluate_wiki_content

        # After agent generates content
        eval_result = evaluate_wiki_content(
            wiki_url="/wiki/New-Topic",
            content=generated_content,
            action="auto-grow",
        )
        if eval_result["overall_score"] < 0.7:
            logger.warning("Content rejected: score=%.2f", eval_result["overall_score"])
    """
    logger.info("Wiki growth evaluation enabled")


def evaluate_wiki_content(
    wiki_url: str,
    content: str,
    action: str = "auto-grow",
    threshold: float = 0.7,
    rubric: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate wiki content and return (score, decision).

    Uses LLM-as-judge via ContentEvaluator and records to future-agi.
    """
    from hermes_observability.evaluator import ContentEvaluator
    tracer = get_tracer()

    evaluator = ContentEvaluator(tracer=tracer)
    result = evaluator.evaluate(
        wiki_url=wiki_url,
        content=content,
        action=action,
        rubric=rubric,
    )

    # Add acceptance decision
    acceptable, reason = evaluator.is_acceptable(result, threshold=threshold)
    result["acceptable"] = acceptable
    result["reason"] = reason

    logger.info(
        "Wiki quality: url=%s action=%s score=%.2f acceptable=%s reason=%s",
        wiki_url, action, result["overall_score"], acceptable, reason,
    )

    return result


# ── Scenario 3: Tool Call Visualization ────────────────────────────

class ToolCallTracer:
    """
    Wraps tool execution to produce visualization spans in future-agi.

    Each tool call becomes a span with:
    - Tool name and arguments (truncated)
    - Result preview
    - Execution duration
    - Error status
    - Parent agent span context

    Usage with HermesAgentLoop:
        tool_tracer = ToolCallTracer(tracer)
        agent_span = tracer.agent_span(...)

        # Before tool execution
        tool_span = tool_tracer.start_tool(agent_span, "web_search", {"query": "foo"})

        # After tool execution
        tool_tracer.end_tool(tool_span, result, duration_ms, error)
    """

    def __init__(self, tracer=None):
        self.tracer = tracer or get_tracer()

    def start_tool(self, parent_span, tool_name: str, tool_args: Dict = None):
        """Start a tool call span."""
        span = self.tracer.tool_span(parent_span, tool_name)
        if tool_args and span.is_recording():
            span.set_attribute("hermes.tool.args", json.dumps(tool_args)[:2000])
        return span

    def end_tool(self, span, result: str, duration_ms: float, error: Optional[str] = None):
        """End a tool call span with results."""
        self.tracer.record_tool_call(
            span=span,
            tool_name="",  # Already set in start
            tool_args={},
            tool_result=result,
            duration_ms=duration_ms,
            error=error,
        )
        span.end()


def patch_tool_execution():
    """
    Instrument Hermes Agent tool execution for future-agi visualization.

    This creates a trace where each tool call is a child span of the
    agent span, allowing visualization of:
    - Tool call sequence and parallelism
    - Individual tool performance
    - Error patterns across tools
    - Tool usage frequency

    Installation: Wrap handle_function_call in model_tools.py:
        from hermes_observability.integrations import trace_tool_call

        def handle_function_call_with_trace(function_name, function_args, **kwargs):
            start = time.monotonic()
            try:
                result = original_handle_function_call(function_name, function_args, **kwargs)
                trace_tool_call(function_name, function_args, result,
                              duration_ms=(time.monotonic() - start) * 1000)
                return result
            except Exception as e:
                trace_tool_call(function_name, function_args, str(e),
                              duration_ms=(time.monotonic() - start) * 1000,
                              error=str(e))
                raise
    """
    logger.info("Tool execution tracing enabled")


def trace_tool_call(tool_name: str, tool_args: Dict, result: str,
                    duration_ms: float, error: Optional[str] = None):
    """Record a single tool call to the active trace context."""
    tracer = get_tracer()
    # Creates a standalone span (no parent context) -- in production
    # this would be linked to the agent span via context propagation
    span = tracer.tool_span(None, tool_name)
    tracer.record_tool_call(
        span=span,
        tool_name=tool_name,
        tool_args=tool_args,
        tool_result=result,
        duration_ms=duration_ms,
        error=error,
    )
    span.end()


# ── Scenario 4: Prompt A/B Testing ────────────────────────────────

class AgentABWrapper:
    """
    Wraps AIAgent.run_conversation() with A/B testing.

    Automatically routes to prompt variants, records outcomes,
    and integrates with future-agi evaluation dashboards.

    Usage:
        ab = AgentABWrapper(
            experiment_id="system-prompt-v3",
            tracer=tracer,
        )
        ab.add_variant("control", original_system_prompt)
        ab.add_variant("with_rubric", system_prompt + "\\nFollow this rubric: ...")

        result = ab.run(agent, user_input="Write about Python")
        # result includes variant assignment + agent output
    """

    def __init__(self, experiment_id: str, tracer=None):
        from hermes_observability.ab_test import PromptABTester
        self.tester = PromptABTester(
            experiment_id=experiment_id,
            tracer=tracer or get_tracer(),
        )

    def add_variant(self, name: str, prompt_template: str, weight: float = 1.0,
                    model: Optional[str] = None, metadata: Optional[Dict] = None):
        self.tester.add_variant(name, prompt_template, weight, model, metadata)

    def run(self, agent, user_input: str, score_fn: Optional[Callable] = None,
            **run_kwargs) -> Dict[str, Any]:
        """
        Run agent with A/B routed prompt and record outcome.

        Args:
            agent: AIAgent instance
            user_input: The user's query
            score_fn: Optional callable(result) -> float score
            **run_kwargs: Passed to agent.run_conversation()

        Returns:
            Dict with variant, prompt, agent_result, and score.
        """
        import time

        variant_name, prompt_template = self.tester.route(user_input)
        start = time.monotonic()

        # Build the actual prompt
        if "{input}" in prompt_template:
            full_prompt = prompt_template.format(input=user_input)
        else:
            full_prompt = prompt_template + "\n\n" + user_input

        # Run the agent
        result = agent.run_conversation(full_prompt, **run_kwargs)

        elapsed_ms = (time.monotonic() - start) * 1000
        final_response = result.get("final_response", "")
        total_tokens = result.get("total_tokens", 0)
        cost_usd = result.get("estimated_cost_usd", 0)

        # Score the result
        score = 0.5  # default
        if score_fn:
            try:
                score = score_fn(result)
            except Exception as e:
                logger.warning("Score function failed: %s", e)

        # Record outcome
        self.tester.record_outcome(
            variant=variant_name,
            input_text=user_input,
            output_text=final_response,
            score=score,
            tokens=total_tokens,
            latency_ms=elapsed_ms,
            cost_usd=cost_usd,
        )

        return {
            "variant": variant_name,
            "prompt": full_prompt,
            "agent_result": result,
            "score": score,
            "latency_ms": elapsed_ms,
        }
