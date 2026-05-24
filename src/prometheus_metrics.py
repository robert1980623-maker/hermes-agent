"""
Prometheus metrics module for daemon-agent.

Provides thread/async-safe metrics collection with Prometheus text format output.
"""

import asyncio
import threading
from collections import defaultdict
from typing import Any, Callable

# ── Thread/Async-Safe Counter ─────────────────────────────────────────────────


class Counter:
    """Thread-safe counter with label support."""

    def __init__(self, name: str, description: str, labelnames: list[str]):
        self._name = name
        self._description = description
        self._labelnames = tuple(labelnames)
        self._lock = threading.Lock()
        self._values: dict[tuple, float] = defaultdict(float)

    def labels(self, **labelvalues) -> "CounterLabel":
        """Return a labeled counter."""
        return CounterLabel(self, labelvalues)

    def _get_value(self, *labelvalues) -> float:
        """Get current value for label combination."""
        with self._lock:
            return self._values[labelvalues]

    def _inc(self, labelvalues: tuple, amount: float = 1.0) -> None:
        """Increment counter (internal, called by CounterLabel)."""
        with self._lock:
            self._values[labelvalues] += amount

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def labelnames(self) -> tuple:
        return self._labelnames

    def _iter_labels(self):
        """Iterate over all label combinations and values."""
        with self._lock:
            for labels, value in self._values.items():
                yield labels, value


class CounterLabel:
    """Labeled counter for incrementing."""

    def __init__(self, counter: Counter, labelvalues: dict):
        self._counter = counter
        self._labelvalues = labelvalues
        self._labeltuple = tuple(labelvalues.get(name) for name in counter.labelnames)

    def inc(self, amount: float = 1.0) -> None:
        """Increment the counter."""
        self._counter._inc(self._labeltuple, amount)

    def _get_label_dict(self) -> dict:
        """Get label values as dict."""
        return self._labelvalues


# ── Histogram ─────────────────────────────────────────────────────────────────


class Histogram:
    """Histogram metric with bucket tracking."""

    def __init__(
        self,
        name: str,
        description: str,
        labelnames: list[str],
        buckets: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    ):
        self._name = name
        self._description = description
        self._labelnames = tuple(labelnames)
        self._buckets = buckets + (float("inf"),)
        self._lock = threading.Lock()
        # Per-label storage: {"labels_tuple": {"count": int, "sum": float, "buckets": {le: count}}}
        self._storage: dict[tuple, dict] = defaultdict(
            lambda: {"count": 0, "sum": 0.0, "buckets": defaultdict(float)}
        )

    def labels(self, **labelvalues) -> "HistogramLabel":
        """Return a labeled histogram."""
        return HistogramLabel(self, labelvalues)

    def _get_count(self, *labelvalues) -> int:
        """Get count for label combination."""
        with self._lock:
            return self._storage[labelvalues]["count"]

    def _get_sum(self, *labelvalues) -> float:
        """Get sum for label combination."""
        with self._lock:
            return self._storage[labelvalues]["sum"]

    def _get_buckets(self, *labelvalues) -> dict:
        """Get bucket counts for label combination."""
        with self._lock:
            return dict(self._storage[labelvalues]["buckets"])

    def _observe(self, labelvalues: tuple, value: float) -> None:
        """Record an observation (internal, called by HistogramLabel)."""
        with self._lock:
            storage = self._storage[labelvalues]
            storage["count"] += 1
            storage["sum"] += value
            for bound in self._buckets:
                if value <= bound:
                    storage["buckets"][bound] += 1

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def labelnames(self) -> tuple:
        return self._labelnames

    @property
    def buckets(self) -> tuple:
        return self._buckets

    def _iter_labels(self):
        """Iterate over all label combinations and data."""
        with self._lock:
            for labels, data in self._storage.items():
                yield labels, data


class HistogramLabel:
    """Labeled histogram for recording observations."""

    def __init__(self, histogram: Histogram, labelvalues: dict):
        self._histogram = histogram
        self._labelvalues = labelvalues
        self._labeltuple = tuple(labelvalues.get(name) for name in histogram.labelnames)

    def observe(self, value: float) -> None:
        """Record an observation."""
        self._histogram._observe(self._labeltuple, value)


# ── Gauge ─────────────────────────────────────────────────────────────────────


class Gauge:
    """Gauge metric with label support."""

    def __init__(self, name: str, description: str, labelnames: list[str]):
        self._name = name
        self._description = description
        self._labelnames = tuple(labelnames)
        self._lock = threading.Lock()
        self._values: dict[tuple, float] = defaultdict(float)

    def labels(self, **labelvalues) -> "GaugeLabel":
        """Return a labeled gauge."""
        return GaugeLabel(self, labelvalues)

    def _get_value(self, *labelvalues) -> float:
        """Get current value for label combination."""
        with self._lock:
            return self._values[labelvalues]

    def _set(self, labelvalues: tuple, value: float) -> None:
        """Set gauge value (internal)."""
        with self._lock:
            self._values[labelvalues] = value

    def _inc(self, labelvalues: tuple = (), amount: float = 1.0) -> None:
        """Increment gauge (internal)."""
        with self._lock:
            self._values[labelvalues] += amount

    def _dec(self, labelvalues: tuple = (), amount: float = 1.0) -> None:
        """Decrement gauge (internal)."""
        with self._lock:
            self._values[labelvalues] -= amount

    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge without labels."""
        self._inc((), amount)

    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge without labels."""
        self._dec((), amount)

    def set(self, value: float) -> None:
        """Set gauge value without labels."""
        self._set((), value)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def labelnames(self) -> tuple:
        return self._labelnames

    def _iter_labels(self):
        """Iterate over all label combinations and values."""
        with self._lock:
            for labels, value in self._values.items():
                yield labels, value


class GaugeLabel:
    """Labeled gauge for operations."""

    def __init__(self, gauge: Gauge, labelvalues: dict):
        self._gauge = gauge
        self._labelvalues = labelvalues
        self._labeltuple = tuple(labelvalues.get(name) for name in gauge.labelnames)

    def set(self, value: float) -> None:
        """Set the gauge value."""
        self._gauge._set(self._labeltuple, value)

    def inc(self, amount: float = 1.0) -> None:
        """Increment the gauge."""
        self._gauge._inc(self._labeltuple, amount)

    def dec(self, amount: float = 1.0) -> None:
        """Decrement the gauge."""
        self._gauge._dec(self._labeltuple, amount)


# ── Prometheus Text Format Generation ────────────────────────────────────────


def _format_labels(labelnames: tuple, labelvalues: tuple) -> str:
    """Format labels for Prometheus output (sorted alphabetically for consistency)."""
    if not labelnames:
        return ""
    # Sort labels alphabetically by name for consistent Prometheus output
    sorted_indices = sorted(range(len(labelnames)), key=lambda i: labelnames[i])
    parts = [f'{labelnames[i]}="{labelvalues[i]}"' for i in sorted_indices]
    return "{" + ",".join(parts) + "}"


def generate_prometheus_text(metrics: list) -> str:
    """
    Generate Prometheus text format output from metrics.

    Args:
        metrics: List of Metric instances (Counter, Histogram, Gauge)

    Returns:
        Prometheus text format string
    """
    lines = []

    for metric in metrics:
        metric_lines = _format_metric(metric)
        lines.extend(metric_lines)

    return "\n".join(lines)


def _format_metric(metric) -> list[str]:
    """Format a single metric into Prometheus text lines."""
    lines = []

    # HELP line
    lines.append(f"# HELP {metric.name} {metric.description}")

    # TYPE line
    if isinstance(metric, Counter):
        metric_type = "counter"
    elif isinstance(metric, Histogram):
        metric_type = "histogram"
    elif isinstance(metric, Gauge):
        metric_type = "gauge"
    else:
        metric_type = "untyped"

    lines.append(f"# TYPE {metric.name} {metric_type}")

    if isinstance(metric, Counter):
        for labels, value in metric._iter_labels():
            label_str = _format_labels(metric.labelnames, labels)
            lines.append(f"{metric.name}{label_str} {value}")

    elif isinstance(metric, Histogram):
        for labels, data in metric._iter_labels():
            label_str = _format_labels(metric.labelnames, labels)
            # Bucket lines - need to prepend le label to existing labels
            for bound in metric.buckets:
                bucket_count = data["buckets"].get(bound, 0)
                if bound == float("inf"):
                    le_str = "+Inf"
                else:
                    le_str = str(bound)
                if label_str:
                    # label_str is like {tool="test"}, we need {le="0.1",tool="test"}
                    # Strip both braces from label_str: {tool="test"} -> tool="test"
                    inner_labels = label_str[1:-1]
                    bucket_line = f"{metric.name}_bucket{{le=\"{le_str}\",{inner_labels}}} {float(bucket_count)}"
                else:
                    bucket_line = f"{metric.name}_bucket{{le=\"{le_str}\"}} {float(bucket_count)}"
                lines.append(bucket_line)
            # Sum and count
            lines.append(f"{metric.name}_sum{label_str} {data['sum']}")
            lines.append(f"{metric.name}_count{label_str} {data['count']}")

    elif isinstance(metric, Gauge):
        for labels, value in metric._iter_labels():
            label_str = _format_labels(metric.labelnames, labels)
            lines.append(f"{metric.name}{label_str} {float(value)}")

    return lines


# ── PrometheusMetrics Singleton ────────────────────────────────────────────────


class PrometheusMetrics:
    """
    Singleton class holding all Prometheus metrics for the daemon-agent.

    Provides:
    - tool_call_total (Counter): Total tool calls with labels (tool_name, status)
    - tool_call_duration_seconds (Histogram): Tool call duration
    - error_rate (Gauge): Current error rate
    - active_agents (Gauge): Number of active agents
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Initialize metrics
        self.tool_call_total = Counter(
            "tool_call_total",
            "Total number of tool calls",
            ["tool_name", "status"],
        )

        self.tool_call_duration_seconds = Histogram(
            "tool_call_duration_seconds",
            "Tool call duration in seconds",
            ["tool_name"],
        )

        self.error_rate = Gauge(
            "error_rate",
            "Current error rate",
            [],
        )

        self.active_agents = Gauge(
            "active_agents",
            "Number of active agents",
            [],
        )

    def record_tool_call(self, tool_name: str, status: str, duration: float) -> None:
        """
        Record a tool call.

        Args:
            tool_name: Name of the tool called
            status: Status of the call ("success" or "error")
            duration: Call duration in seconds
        """
        self.tool_call_total.labels(tool_name=tool_name, status=status).inc()
        self.tool_call_duration_seconds.labels(tool_name=tool_name).observe(duration)

    def set_error_rate(self, rate: float) -> None:
        """Set the current error rate."""
        self.error_rate.labels().set(rate)

    def set_active_agents(self, count: int) -> None:
        """Set the number of active agents."""
        self.active_agents.labels().set(float(count))

    def get_all_metrics(self) -> list:
        """Get all metrics for text generation."""
        return [
            self.tool_call_total,
            self.tool_call_duration_seconds,
            self.error_rate,
            self.active_agents,
        ]

    def get_app(self) -> Callable:
        """
        Get an ASGI app for the /metrics endpoint.

        Returns a callable that handles ASGI scope/receive/send.
        """
        return MetricsASGIApp(self)


class MetricsASGIApp:
    """ASGI app for serving Prometheus metrics."""

    def __init__(self, metrics: PrometheusMetrics):
        self._metrics = metrics

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """Handle an ASGI request."""
        if scope["type"] != "http":
            await send({"type": "http.response.start", "status": 400, "headers": []})
            await send({"type": "http.response.body", "body": b"Expected HTTP request"})
            return

        path = scope.get("path", "")

        if path == "/metrics":
            # Generate metrics output
            output = generate_prometheus_text(self._metrics.get_all_metrics())
            body = output.encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/plain; version=0.0.4; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
        else:
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-type", b"text/plain")],
            })
            await send({"type": "http.response.body", "body": b"Not Found"})
