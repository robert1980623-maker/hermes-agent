"""
PromptABTester -- A/B testing for prompt optimization in Hermes Agent.

Routes agent requests to different prompt variants, collects metrics,
and reports results to future-agi for statistical analysis.
"""

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PromptVariant:
    """Defines a single prompt variant in an A/B test."""

    def __init__(self, name: str, prompt_template: str, weight: float = 1.0,
                 model: Optional[str] = None, metadata: Optional[Dict] = None):
        self.name = name
        self.prompt_template = prompt_template
        self.weight = weight
        self.model = model
        self.metadata = metadata or {}


class PromptABTester:
    """
    A/B testing framework for prompt optimization.

    Integrates with future-agi to:
    - Track variant assignments as span attributes
    - Store evaluation results in future-agi datasets
    - Visualize win/loss metrics in the dashboard

    Usage:
        tester = PromptABTester(experiment_id="prompt-v2")
        tester.add_variant("control", "You are a helpful assistant...")
        tester.add_variant("experimental", "You are an expert wiki editor...")

        # Route a request
        variant, prompt = tester.route(user_input="write about Python")
        result = agent.run_conversation(prompt)

        # Record the outcome
        tester.record_outcome(
            variant=variant,
            input_text=user_input,
            output_text=result["final_response"],
            score=0.85,  # from human eval or LLM judge
            tokens=result.get("total_tokens", 0),
        )

        # Get results
        stats = tester.get_stats()
    """

    def __init__(
        self,
        experiment_id: str,
        tracer=None,
        routing_strategy: str = "weighted_random",
    ):
        self.experiment_id = experiment_id
        self.variants: Dict[str, PromptVariant] = {}
        self.tracer = tracer
        self.routing_strategy = routing_strategy
        self._outcomes: List[Dict[str, Any]] = []
        self._total_weight = 0.0

    def add_variant(self, name: str, prompt_template: str, weight: float = 1.0,
                    model: Optional[str] = None, metadata: Optional[Dict] = None):
        """Add a prompt variant to the experiment."""
        variant = PromptVariant(name, prompt_template, weight, model, metadata)
        self.variants[name] = variant
        self._total_weight += weight

    def route(self, user_input: str, session_id: Optional[str] = None) -> Tuple[str, str]:
        """
        Route a request to a variant based on the routing strategy.

        Returns (variant_name, rendered_prompt).
        """
        if not self.variants:
            raise ValueError("No variants registered")

        # Deterministic routing: same input -> same variant (sticky)
        if session_id:
            bucket = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
        else:
            bucket = int(hashlib.md5(user_input.encode()).hexdigest(), 16)

        if self.routing_strategy == "weighted_random":
            threshold = bucket % int(self._total_weight * 100)
            cumulative = 0
            for name, v in self.variants.items():
                cumulative += int(v.weight * 100)
                if threshold < cumulative:
                    return name, v.prompt_template
        elif self.routing_strategy == "round_robin":
            names = list(self.variants.keys())
            idx = bucket % len(names)
            chosen = names[idx]
            return chosen, self.variants[chosen].prompt_template
        elif self.routing_strategy == "uniform":
            names = list(self.variants.keys())
            idx = bucket % len(names)
            chosen = names[idx]
            return chosen, self.variants[chosen].prompt_template

        # Fallback: first variant
        name = next(iter(self.variants))
        return name, self.variants[name].prompt_template

    def render_prompt(self, variant_name: str, **kwargs) -> str:
        """Render a prompt template with the given variables."""
        variant = self.variants.get(variant_name)
        if not variant:
            raise ValueError(f"Unknown variant: {variant_name}")
        return variant.prompt_template.format(**kwargs)

    def record_outcome(
        self,
        variant: str,
        input_text: str,
        output_text: str,
        score: float,
        tokens: int = 0,
        latency_ms: float = 0,
        cost_usd: float = 0,
        tool_calls: int = 0,
        custom_metrics: Optional[Dict[str, Any]] = None,
    ):
        """
        Record an outcome for a variant assignment.

        The score can come from:
        - Human evaluation
        - LLM-as-judge (use ContentEvaluator)
        - Automated metrics (exact match, BLEU, etc.)
        """
        outcome = {
            "experiment_id": self.experiment_id,
            "variant": variant,
            "timestamp": time.time(),
            "input_preview": input_text[:500],
            "output_preview": output_text[:1000],
            "score": score,
            "tokens": tokens,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "tool_calls": tool_calls,
            "custom_metrics": custom_metrics or {},
        }
        self._outcomes.append(outcome)

        # Report to future-agi via tracer
        if self.tracer:
            # We record this as a span with variant and score attributes
            # so it appears in future-agi's evaluation dashboard
            pass  # tracer integration done in agent_span context

        logger.debug(
            "AB outcome: exp=%s variant=%s score=%.3f tokens=%d",
            self.experiment_id, variant, score, tokens,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all variants."""
        stats = {"experiment_id": self.experiment_id, "variants": {}}
        for name in self.variants:
            outcomes = [o for o in self._outcomes if o["variant"] == name]
            if not outcomes:
                stats["variants"][name] = {
                    "count": 0, "avg_score": 0, "avg_tokens": 0,
                    "avg_latency_ms": 0, "total_cost_usd": 0,
                }
                continue
            scores = [o["score"] for o in outcomes]
            tokens = [o["tokens"] for o in outcomes if o["tokens"] > 0]
            latencies = [o["latency_ms"] for o in outcomes if o["latency_ms"] > 0]
            costs = [o["cost_usd"] for o in outcomes]
            stats["variants"][name] = {
                "count": len(outcomes),
                "avg_score": round(sum(scores) / len(scores), 3),
                "min_score": round(min(scores), 3),
                "max_score": round(max(scores), 3),
                "avg_tokens": round(sum(tokens) / len(tokens), 1) if tokens else 0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "total_cost_usd": round(sum(costs), 4),
            }
        stats["total_outcomes"] = len(self._outcomes)
        return stats

    def save_results(self, path: Optional[str] = None) -> str:
        """Save A/B test results to a JSON file."""
        path = path or os.path.join(
            os.getenv("HERMES_HOME", os.path.expanduser("~/.hermes")),
            f"ab_test_{self.experiment_id}.json",
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "experiment_id": self.experiment_id,
            "variants": {n: {
                "prompt_template": v.prompt_template,
                "weight": v.weight,
                "model": v.model,
            } for n, v in self.variants.items()},
            "stats": self.get_stats(),
            "outcomes": self._outcomes,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("A/B test results saved to %s", path)
        return path

    def export_for_futureagi(self) -> Dict[str, Any]:
        """
        Export results in a format suitable for future-agi evaluation ingestion.

        future-agi expects dataset rows with:
        - input: the user input
        - output: the model output
        - score: evaluation score
        - metadata: additional context
        """
        rows = []
        for o in self._outcomes:
            rows.append({
                "experiment_id": self.experiment_id,
                "variant": o["variant"],
                "input": o["input_preview"],
                "output": o["output_preview"],
                "score": o["score"],
                "metadata": {
                    "tokens": o["tokens"],
                    "latency_ms": o["latency_ms"],
                    "cost_usd": o["cost_usd"],
                    "tool_calls": o["tool_calls"],
                    "custom_metrics": o["custom_metrics"],
                },
            })
        return {
            "experiment_id": self.experiment_id,
            "rows": rows,
            "stats": self.get_stats(),
        }
