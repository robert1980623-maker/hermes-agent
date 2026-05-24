"""Tests for Prometheus metrics module."""

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest

from src.prometheus_metrics import (
    Counter,
    Gauge,
    Histogram,
    PrometheusMetrics,
    generate_prometheus_text,
)


# ── Counter Tests ─────────────────────────────────────────────────────────────


def test_counter_labels():
    """Counter should support tool_name and status labels."""
    counter = Counter("tool_call_total", "Total tool calls", ["tool_name", "status"])
    counter.labels(tool_name="test_tool", status="success").inc()
    counter.labels(tool_name="test_tool", status="success").inc()
    counter.labels(tool_name="test_tool", status="error").inc()

    # Verify internal storage
    assert counter._get_value("test_tool", "success") == 2
    assert counter._get_value("test_tool", "error") == 1
    assert counter._get_value("other_tool", "success") == 0


def test_counter_inc_without_labels():
    """Counter should track total without labels."""
    counter = Counter("tool_call_total", "Total tool calls", ["tool_name", "status"])
    counter.labels(tool_name="test_tool", status="success").inc(5)

    assert counter._get_value("test_tool", "success") == 5


def test_counter_thread_safety():
    """Counter increments should be thread-safe."""
    counter = Counter("tool_call_total", "Total tool calls", ["tool_name", "status"])

    def increment():
        for _ in range(100):
            counter.labels(tool_name="test", status="ok").inc()
            time.sleep(0.001)

    threads = [threading.Thread(target=increment) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter._get_value("test", "ok") == 1000


def test_counter_async_safety():
    """Counter increments should be async-safe."""
    counter = Counter("tool_call_total", "Total tool calls", ["tool_name", "status"])

    async def increment():
        for _ in range(100):
            counter.labels(tool_name="test", status="ok").inc()
            await asyncio.sleep(0.001)

    async def run():
        await asyncio.gather(*[increment() for _ in range(10)])

    asyncio.run(run())

    assert counter._get_value("test", "ok") == 1000


# ── Histogram Tests ───────────────────────────────────────────────────────────


def test_histogram_record():
    """Histogram should record values."""
    histogram = Histogram(
        "tool_call_duration_seconds",
        "Tool call duration in seconds",
        ["tool_name"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    )
    histogram.labels(tool_name="test").observe(0.1)
    histogram.labels(tool_name="test").observe(0.05)

    # Verify sum and count
    assert histogram._get_count("test") == 2
    assert histogram._get_sum("test") == pytest.approx(0.15)


def test_histogram_buckets():
    """Histogram should track bucket counts."""
    histogram = Histogram(
        "tool_call_duration_seconds",
        "Tool call duration in seconds",
        ["tool_name"],
        buckets=(0.01, 0.1, 1.0),
    )
    histogram.labels(tool_name="test").observe(0.005)  # < 0.01
    histogram.labels(tool_name="test").observe(0.05)  # < 0.1
    histogram.labels(tool_name="test").observe(0.5)  # < 1.0
    histogram.labels(tool_name="test").observe(2.0)  # >= 1.0

    buckets = histogram._get_buckets("test")
    assert buckets[0.01] == 1  # 0.005 <= 0.01
    assert buckets[0.1] == 2  # 0.005, 0.05 <= 0.1
    assert buckets[1.0] == 3  # 0.005, 0.05, 0.5 <= 1.0
    assert buckets[float("inf")] == 4  # all


# ── Gauge Tests ───────────────────────────────────────────────────────────────


def test_gauge_set():
    """Gauge should allow setting values."""
    gauge = Gauge("active_agents", "Number of active agents", ["agent_type"])
    gauge.labels(agent_type="worker").set(5)
    gauge.labels(agent_type="manager").set(2)

    assert gauge._get_value("worker") == 5
    assert gauge._get_value("manager") == 2


def test_gauge_inc_dec():
    """Gauge should support increment and decrement."""
    gauge = Gauge("error_rate", "Current error rate", [])
    gauge.inc()
    gauge.inc()
    gauge.dec()

    assert gauge._get_value() == 1


def test_gauge_thread_safety():
    """Gauge operations should be thread-safe."""
    gauge = Gauge("active_agents", "Number of active agents", ["agent_type"])

    def modify():
        for _ in range(100):
            gauge.labels(agent_type="test").inc()
            time.sleep(0.001)

    threads = [threading.Thread(target=modify) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert gauge._get_value("test") == 1000


# ── PrometheusMetrics Singleton Tests ────────────────────────────────────────


def test_metrics_singleton():
    """PrometheusMetrics should be a singleton."""
    metrics1 = PrometheusMetrics()
    metrics2 = PrometheusMetrics()

    assert metrics1 is metrics2


def test_metrics_has_required_metrics():
    """PrometheusMetrics should expose all required metrics."""
    metrics = PrometheusMetrics()

    assert metrics.tool_call_total is not None
    assert isinstance(metrics.tool_call_total, Counter)
    assert metrics.tool_call_duration_seconds is not None
    assert isinstance(metrics.tool_call_duration_seconds, Histogram)
    assert metrics.error_rate is not None
    assert isinstance(metrics.error_rate, Gauge)
    assert metrics.active_agents is not None
    assert isinstance(metrics.active_agents, Gauge)


def test_metrics_record_tool_call():
    """Metrics should record tool calls correctly."""
    metrics = PrometheusMetrics()

    metrics.record_tool_call("test_tool", "success", 0.1)
    metrics.record_tool_call("test_tool", "error", 0.05)

    # Check counter
    assert metrics.tool_call_total._get_value("test_tool", "success") == 1
    assert metrics.tool_call_total._get_value("test_tool", "error") == 1

    # Check histogram
    assert metrics.tool_call_duration_seconds._get_count("test_tool") == 2
    assert metrics.tool_call_duration_seconds._get_sum("test_tool") == pytest.approx(0.15)


def test_metrics_set_error_rate():
    """Metrics should set error rate."""
    metrics = PrometheusMetrics()
    metrics.set_error_rate(0.05)

    assert metrics.error_rate._get_value() == 0.05


def test_metrics_set_active_agents():
    """Metrics should set active agents count."""
    metrics = PrometheusMetrics()
    metrics.set_active_agents(10)

    assert metrics.active_agents._get_value() == 10


# ── Text Format Generation Tests ─────────────────────────────────────────────


def test_generate_prometheus_text_single_metric():
    """generate_prometheus_text should output valid Prometheus text format."""
    counter = Counter("test_counter", "A test counter", ["label"])
    counter.labels(label="value").inc()

    output = generate_prometheus_text([counter])

    assert "# HELP test_counter A test counter" in output
    assert "# TYPE test_counter counter" in output
    assert 'test_counter{label="value"} 1.0' in output


def test_generate_prometheus_text_histogram_format():
    """Histogram output should follow Prometheus convention."""
    histogram = Histogram(
        "test_histogram",
        "A test histogram",
        ["tool"],
        buckets=(0.1, 1.0),
    )
    histogram.labels(tool="test").observe(0.5)

    output = generate_prometheus_text([histogram])

    assert "# HELP test_histogram A test histogram" in output
    assert "# TYPE test_histogram histogram" in output
    assert 'test_histogram_bucket{le="0.1",tool="test"} 0.0' in output
    assert 'test_histogram_bucket{le="1.0",tool="test"} 1.0' in output
    assert 'test_histogram_bucket{le="+Inf",tool="test"} 1.0' in output
    assert 'test_histogram_sum{tool="test"} 0.5' in output
    assert 'test_histogram_count{tool="test"} 1' in output


def test_generate_prometheus_text_gauge_format():
    """Gauge output should follow Prometheus convention."""
    gauge = Gauge("test_gauge", "A test gauge", ["env"])
    gauge.labels(env="prod").set(42)

    output = generate_prometheus_text([gauge])

    assert "# HELP test_gauge A test gauge" in output
    assert "# TYPE test_gauge gauge" in output
    assert 'test_gauge{env="prod"} 42.0' in output


def test_generate_prometheus_text_empty():
    """generate_prometheus_text should handle empty metric list."""
    output = generate_prometheus_text([])

    assert output == ""


def test_generate_prometheus_text_all_metrics():
    """generate_prometheus_text should handle all metrics together."""
    metrics = PrometheusMetrics()

    metrics.record_tool_call("my_tool", "success", 0.1)
    metrics.set_error_rate(0.02)
    metrics.set_active_agents(5)

    output = generate_prometheus_text(metrics.get_all_metrics())

    # Check tool_call_total
    assert "tool_call_total" in output
    assert 'tool_call_total{status="success",tool_name="my_tool"}' in output

    # Check tool_call_duration_seconds
    assert "tool_call_duration_seconds" in output
    assert "tool_call_duration_seconds_bucket" in output

    # Check error_rate
    assert "error_rate" in output
    assert 'error_rate 0.02' in output

    # Check active_agents
    assert "active_agents" in output
    assert 'active_agents 5.0' in output


# ── HTTP Handler Tests ────────────────────────────────────────────────────────


def test_metrics_app():
    """PrometheusMetrics should provide a ASGI/WSGI compatible app."""
    metrics = PrometheusMetrics()
    metrics.record_tool_call("test", "success", 0.1)

    app = metrics.get_app()

    # Should be a callable that takes scope, receive, send
    assert callable(app)


def test_metrics_app_response_format():
    """Metrics app should return Prometheus text format."""
    metrics = PrometheusMetrics()
    metrics.record_tool_call("test", "success", 0.1)

    app = metrics.get_app()

    # Mock ASGI scope
    scope = {"type": "http", "path": "/metrics", "method": "GET"}

    # Collect response
    response_body = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        if message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    # Run the app
    import asyncio

    async def run():
        await app(scope, receive, send)

    asyncio.run(run())

    body = b"".join(response_body).decode("utf-8")

    assert "# HELP tool_call_total" in body
    assert 'tool_call_total{status="success",tool_name="test"}' in body


def test_metrics_app_404_for_other_paths():
    """Metrics app should return 404 for non-/metrics paths."""
    metrics = PrometheusMetrics()
    app = metrics.get_app()

    scope = {"type": "http", "path": "/other", "method": "GET"}

    status_code = None

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]

    async def run():
        await app(scope, receive, send)

    asyncio.run(run())

    assert status_code == 404
