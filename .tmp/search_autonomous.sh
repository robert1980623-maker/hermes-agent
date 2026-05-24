#!/bin/bash
curl -s "https://api.github.com/search/repositories?q=autonomous+agent&created=>2026-04-11&sort=stars&order=desc&per_page=20" > /tmp/autonomous_results.json
