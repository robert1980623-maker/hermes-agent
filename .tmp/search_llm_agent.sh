#!/bin/bash
curl -s "https://api.github.com/search/repositories?q=LLM+agent&created=>2026-04-11&sort=stars&order=desc&per_page=20" > /tmp/llm_agent_results.json
