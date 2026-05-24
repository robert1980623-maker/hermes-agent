"""
Concrete code examples for integrating Hermes Agent with future-agi.
"""

EXAMPLE_1 = """
# In cron/scheduler.py tick():
from hermes_observability.integrations import record_cron_patrol
success, output, final_response, error = run_job(job)
record_cron_patrol(job, success, final_response, error)
"""

EXAMPLE_2 = """
# Wiki content quality evaluation:
from hermes_observability.integrations import evaluate_wiki_content
result = evaluate_wiki_content(wiki_url="/wiki/Topic", content=text, threshold=0.7)
if result["acceptable"]: save_to_wiki(wiki_url, text)
"""

EXAMPLE_3 = """
# Tool call tracing wrapper:
from hermes_observability.integrations import trace_tool_call
trace_tool_call("web_search", {"q": "foo"}, result, duration_ms=500)
"""

EXAMPLE_4 = """
# A/B testing:
from hermes_observability.integrations import AgentABWrapper
ab = AgentABTracker(experiment_id="prompt-v3")
ab.add_variant("control", "You are Hermes Agent")
ab.add_variant("enhanced", "You are Hermes Agent. Think step by step.")
result = ab.run(agent, "query", score_fn=my_scoring)
"""