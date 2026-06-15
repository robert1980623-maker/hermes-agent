#!/usr/bin/env python3
"""Search arXiv API for latest papers on LLM agent, multi-agent, autonomous agent."""

import urllib.request
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import concurrent.futures

ATOM_NS = "{http://www.w3.org/2005/Atom}"

QUERIES = [
    'ti:agent+AND+cat:cs.AI',
    'ti:agent+AND+cat:cs.LG',
    'ti:agent+AND+cat:cs.CL',
    'ti:multi-agent+AND+cat:cs.AI',
    'ti:autonomous+AND+cat:cs.AI',
    'abs:"LLM+agent"+AND+cat:cs.AI',
    'abs:"LLM+agent"+AND+cat:cs.LG',
]

def parse_arxiv_xml(data):
    root = ET.fromstring(data)
    papers = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        arxiv_id = entry.find(f"{ATOM_NS}id").text.split("/abs/")[-1]
        title = entry.find(f"{ATOM_NS}title").text.strip().replace("\n", " ")
        authors = [a.find(f"{ATOM_NS}name").text for a in entry.findall(f"{ATOM_NS}author")]
        published = entry.find(f"{ATOM_NS}published").text
        summary = entry.find(f"{ATOM_NS}summary").text.strip().replace("\n", " ")
        categories = [c.get("term") for c in entry.findall(f"{ATOM_NS}category")]
        pdf_link = None
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("title") == "pdf":
                pdf_link = link.get("href")
                break
        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": published,
            "categories": categories,
            "abstract": summary[:300],
            "pdf_link": pdf_link,
        })
    return papers

def fetch_query(query):
    url = f"https://export.arxiv.org/api/query?search_query={query}&max_results=10&sortBy=submittedDate&sortOrder=descending"
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'ResearchBot/1.0')
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode('utf-8')
        papers = parse_arxiv_xml(data)
        return query, papers, None
    except Exception as e:
        return query, [], str(e)

def filter_recent(papers, days=3):
    cutoff = datetime.utcnow() - timedelta(days=days)
    return [p for p in papers if datetime.strptime(p["published"][:10], "%Y-%m-%d") >= cutoff]

def is_relevant(paper):
    text = (paper["title"] + " " + paper["abstract"]).lower()
    keywords = [
        "llm agent", "large language model agent", "multi-agent", "multi agent",
        "autonomous agent", "agent-based", "agent framework", "agent system",
        "agent collaboration", "llm-based agent", "agent planning", "agent reasoning",
        "embodied agent", "conversational agent", "intelligent agent",
        "agent architecture", "agent evaluation", "agent benchmark",
        "tool-using agent", "generative agent", "web agent", "coding agent",
    ]
    return any(kw in text for kw in keywords) or "agent" in paper["title"].lower()

def main():
    all_papers = []
    
    # Sequential with sleep (arXiv rate limits)
    for i, query in enumerate(QUERIES):
        print(f"[{i+1}/{len(QUERIES)}] {query}")
        _, papers, err = fetch_query(query)
        if err:
            print(f"  Error: {err}")
        else:
            print(f"  Found {len(papers)} papers")
            all_papers.extend(papers)
        if i < len(QUERIES) - 1:
            time.sleep(3.5)

    print(f"\nTotal: {len(all_papers)}")
    
    # Deduplicate
    seen = set()
    unique = []
    for p in all_papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)
    print(f"Unique: {len(unique)}")
    
    recent = filter_recent(unique, days=3)
    print(f"Last 3 days: {len(recent)}")
    
    relevant = [p for p in recent if is_relevant(p)]
    print(f"Relevant: {len(relevant)}")
    relevant.sort(key=lambda x: x["published"], reverse=True)

    with open("/Users/rowang/projects/hermes-agent/arxiv_results/papers.json", "w") as f:
        json.dump(relevant, f, indent=2)

    print(f"\n{'='*80}")
    print(f"FOUND {len(relevant)} RELEVANT PAPERS (last 3 days)")
    print(f"{'='*80}\n")
    for i, p in enumerate(relevant, 1):
        print(f"[{i}] {p['title']}")
        print(f"    ID: {p['arxiv_id']}")
        print(f"    Authors: {', '.join(p['authors'][:3])}{' et al.' if len(p['authors']) > 3 else ''}")
        print(f"    Date: {p['published'][:10]}")
        print(f"    Cats: {', '.join(p['categories'][:4])}")
        print(f"    Abstract: {p['abstract'][:200]}...")
        print(f"    PDF: {p['pdf_link']}")
        print()

if __name__ == "__main__":
    main()
