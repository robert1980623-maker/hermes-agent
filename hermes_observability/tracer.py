"""
HermesTracer -- OpenTelemetry instrumentation layer for Hermes Agent.

Sends spans to future-agi OTLP endpoint. Wraps AIAgent tool-calling loop,
cron job execution, and platform adapters to produce structured traces.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_otel_initialized = False
_tracer_provider = None
_tracer = None
_StatusCode = None
_trace_mod = None


def _init_otel(endpoint=None, service_name="hermes-agent"):
    """Initialize OpenTelemetry SDK pointing at future-agi OTLP endpoint."""
    global _otel_initialized, _tracer_provider, _tracer, _StatusCode, _trace_mod
    if _otel_initialized:
        return
    endpoint = endpoint or os.getenv("FUTUREAGI_OTLP_ENDPOINT", "http://localhost:4318")
    try:
        from opentelemetry import trace as _t
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.trace import StatusCode as _SC

        _trace_mod = _t
        _StatusCode = _SC
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.getenv("HERMES_VERSION", "dev"),
        })
        _tracer_provider = TracerProvider(resource=resource)
        headers = {}
        api_key = os.getenv("FUTUREAGI_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces",
            headers=headers,
            timeout=10,
        )
        _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        _t.set_tracer_provider(_tracer_provider)
        _tracer = _t.get_tracer("hermes-agent")
        _otel_initialized = True
        logger.info("HermesTracer initialized -- endpoint=%s", endpoint)
    except ImportError:
        logger.warning("opentelemetry SDK not installed -- traces disabled")
        _otel_initialized = True
    except Exception as e:
        logger.error("Failed to init OTel tracer: %s", e)
        _otel_initialized = True


class HermesSpanAttrs:
    """Hermes-specific span attribute keys aligned with future-agi semantic conventions."""
    HERMES_SESSION_ID = "hermes.session_id"
    HERMES_PLATFORM = "hermes.platform"
    HERMES_JOB_ID = "hermes.cron_job_id"
    HERMES_JOB_NAME = "hermes.cron_job_name"
    HERMES_MODEL = "hermes.model"
    HERMES_PROVIDER = "hermes.provider"
    HERMES_SKILLS = "hermes.skills"
    HERMES_TOOL_NAME = "hermes.tool.name"
    HERMES_TOOL_ARGS = "hermes.tool.args"
    HERMES_TOOL_RESULT_PREVIEW = "hermes.tool.result_preview"
    HERMES_TOOL_STATUS = "hermes.tool.status"
    HERMES_TOOL_DURATION_MS = "hermes.tool.duration_ms"
    HERMES_TOOL_ERROR = "hermes.tool.error"
    HERMES_TURN_NUMBER = "hermes.turn.number"
    HERMES_TURN_REASONING = "hermes.turn.reasoning"
    HERMES_TURN_FINISH_REASON = "hermes.turn.finish_reason"
    HERMES_COST_USD = "hermes.cost.usd"
    HERMES_INPUT_TOKENS = "hermes.tokens.input"
    HERMES_OUTPUT_TOKENS = "hermes.tokens.output"
    HERMES_PROMPT_VARIANT = "hermes.prompt.variant"
    HERMES_WIKI_URL = "hermes.wiki.url"
    HERMES_WIKI_ACTION = "hermes.wiki.action"
    HERMES_CONTENT_SCORE = "hermes.content.score"
    HERMES_CONTENT_DIMENSIONS = "hermes.content.dimensions"


class _NoOpSpan:
    """Null object for spans when tracing is disabled."""
    def set_attribute(self, key, value): pass
    def set_status(self, status, desc=None): pass
    def end(self): pass
    def add_event(self, name, attrs=None): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def is_recording(self): return False


class _NoOpTracer:
    def start_span(self, name, attributes=None, context=None):
        return _NoOpSpan()


class HermesTracer:
    """
    Wraps Hermes Agent execution with OpenTelemetry spans.

    Usage:
        tracer = HermesTracer()
        with tracer.agent_span(session_id="xyz", model="gpt-4") as span:
            result = agent.run_conversation("do something")
        tracer.flush()
    """

    def __init__(self, endpoint=None, service_name="hermes-agent", enabled=None):
        self.enabled = enabled if enabled is not None else bool(
            os.getenv("HERMES_OBSERVABILITY_ENABLED", "1")
        )
        self.endpoint = endpoint or os.getenv("FUTUREAGI_OTLP_ENDPOINT")
        self.service_name = service_name
        if self.enabled:
            _init_otel(self.endpoint, self.service_name)

    # -- helpers --
    def _get_tracer(self):
        global _tracer
        if _tracer is None:
            _init_otel()
        if _tracer is None:
            return _NoOpTracer()
        return _tracer

    def _get_status_code(self):
        global _StatusCode
        if _StatusCode is None:
            _init_otel()
        return _StatusCode

    # -- span factories --

    def agent_span(self, session_id, model, platform="cli",
                   provider=None, cron_job_id=None, cron_job_name=None,
                   skills=None, prompt_variant=None):
        if not self.enabled:
            return _NoOpSpan()
        attrs = {
            HermesSpanAttrs.HERMES_SESSION_ID: session_id,
            HermesSpanAttrs.HERMES_MODEL: model,
            HermesSpanAttrs.HERMES_PLATFORM: platform,
            HermesSpanAttrs.HERMES_PROVIDER: provider or "unknown",
            "gen_ai.operation.name": "chat",
        }
        if cron_job_id:
            attrs[HermesSpanAttrs.HERMES_JOB_ID] = cron_job_id
        if cron_job_name:
            attrs[HermesSpanAttrs.HERMES_JOB_NAME] = cron_job_name
        if skills:
            attrs[HermesSpanAttrs.HERMES_SKILLS] = json.dumps(skills)
        if prompt_variant:
            attrs[HermesSpanAttrs.HERMES_PROMPT_VARIANT] = prompt_variant
        return self._get_tracer().start_span("hermes.agent_run", attributes=attrs)

    def tool_span(self, parent_span, tool_name):
        if not self.enabled or not parent_span:
            return _NoOpSpan()
        ctx = None
        if _trace_mod and parent_span.is_recording():
            ctx = _trace_mod.set_span_in_context(parent_span)
        return self._get_tracer().start_span(
            f"hermes.tool.{tool_name}",
            attributes={
                HermesSpanAttrs.HERMES_TOOL_NAME: tool_name,
                "gen_ai.operation.name": "execute_tool",
            },
            context=ctx,
        )

    # -- recording helpers --

    def record_tool_call(self, span, tool_name, tool_args, tool_result,
                         duration_ms, error=None):
        if not self.enabled or not span or not span.is_recording():
            return
        args_preview = json.dumps(tool_args, ensure_ascii=False)[:2000]
        result_preview = tool_result[:2000] if tool_result else ""
        span.set_attribute(HermesSpanAttrs.HERMES_TOOL_ARGS, args_preview)
        span.set_attribute(HermesSpanAttrs.HERMES_TOOL_RESULT_PREVIEW, result_preview)
        span.set_attribute(HermesSpanAttrs.HERMES_TOOL_DURATION_MS, round(duration_ms, 1))
        span.set_attribute(HermesSpanAttrs.HERMES_TOOL_STATUS, "error" if error else "success")
        if error:
            span.set_attribute(HermesSpanAttrs.HERMES_TOOL_ERROR, error)
            sc = self._get_status_code()
            if sc:
                span.set_status(sc.ERROR, error)

    def record_turn(self, span, turn_number, reasoning=None,
                    finish_reason=None, input_tokens=0, output_tokens=0, cost_usd=None):
        if not self.enabled or not span or not span.is_recording():
            return
        span.set_attribute(HermesSpanAttrs.HERMES_TURN_NUMBER, turn_number)
        if reasoning:
            span.set_attribute(HermesSpanAttrs.HERMES_TURN_REASONING, reasoning[:1000])
        if finish_reason:
            span.set_attribute(HermesSpanAttrs.HERMES_TURN_FINISH_REASON, finish_reason)
        if input_tokens:
            span.set_attribute(HermesSpanAttrs.HERMES_INPUT_TOKENS, input_tokens)
        if output_tokens:
            span.set_attribute(HermesSpanAttrs.HERMES_OUTPUT_TOKENS, output_tokens)
        if cost_usd is not None:
            span.set_attribute(HermesSpanAttrs.HERMES_COST_USD, round(cost_usd, 6))

    # -- Scenario 1: cron patrol decision tracing --

    def record_cron_patrol(self, job_id, job_name, prompt, final_response,
                           success, error=None, script_output=None,
                           model=None, session_id=None):
        """Record a complete cron patrol as a trace in future-agi."""
        if not self.enabled:
            return
        sid = session_id or f"cron_{job_id}_{int(time.time())}"
        attrs = {
            HermesSpanAttrs.HERMES_JOB_ID: job_id,
            HermesSpanAttrs.HERMES_JOB_NAME: job_name,
            HermesSpanAttrs.HERMES_PLATFORM: "cron",
            "hermes.cron.prompt_preview": prompt[:1000],
            "hermes.cron.response_preview": final_response[:2000] if final_response else "",
            "hermes.cron.success": success,
            "gen_ai.operation.name": "agent",
        }
        if model:
            attrs[HermesSpanAttrs.HERMES_MODEL] = model
        if script_output:
            attrs["hermes.cron.script_output_preview"] = script_output[:1000]
        span = self._get_tracer().start_span("hermes.cron_patrol", attributes=attrs)
        if error:
            span.set_attribute("hermes.cron.error", error)
            sc = self._get_status_code()
            if sc:
                span.set_status(sc.ERROR, error)
        span.end()

    # -- Scenario 2: wiki content quality eval --

    def record_wiki_quality(self, wiki_url, action, content, score,
                            dimensions, model="evaluator"):
        """Record wiki auto-grow quality evaluation in future-agi."""
        if not self.enabled:
            return
        span = self._get_tracer().start_span(
            "hermes.wiki_quality_eval",
            attributes={
                HermesSpanAttrs.HERMES_WIKI_URL: wiki_url,
                HermesSpanAttrs.HERMES_WIKI_ACTION: action,
                HermesSpanAttrs.HERMES_CONTENT_SCORE: score,
                HermesSpanAttrs.HERMES_CONTENT_DIMENSIONS: json.dumps(dimensions),
                HermesSpanAttrs.HERMES_MODEL: model,
                "hermes.wiki.content_preview": content[:2000],
                "gen_ai.operation.name": "evaluate",
            },
        )
        span.end()

    def flush(self):
        if not self.enabled or not _tracer_provider:
            return
        try:
            _tracer_provider.force_flush(timeout_seconds=5)
        except Exception as e:
            logger.warning("Failed to flush tracer: %s", e)

    def shutdown(self):
        if not self.enabled or not _tracer_provider:
            return
        try:
            _tracer_provider.shutdown()
        except Exception:
            pass
