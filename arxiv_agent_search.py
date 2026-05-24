import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
import re

ATOM_NS = "http://www.w3.org/2005/Atom"

def search_arxiv(query, max_results=5):
    """Search arXiv API for a query, sorted by submittedDate descending."""
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results),
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "HermesAgent/1.0 (https://nousresearch.com; agent@hermes.ai)")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode("utf-8")
        root = ET.fromstring(data)
    except Exception as e:
        print(f"  [ERROR] Query failed: {e}")
        return []

    entries = root.findall(f"{{{ATOM_NS}}}entry")
    results = []
    for entry in entries:
        arxiv_id_raw = entry.find(f"{{{ATOM_NS}}}id").text
        # Extract clean arxiv ID like 2505.XXXXX
        arxiv_id = arxiv_id_raw.split("/abs/")[-1] if "/abs/" in arxiv_id_raw else arxiv_id_raw
        title = entry.find(f"{{{ATOM_NS}}}title").text.strip().replace("\n", " ")

        authors_el = entry.findall(f"{{{ATOM_NS}}}author")
        author_names = [a.find(f"{{{ATOM_NS}}}name").text for a in authors_el]
        first_3 = ", ".join(author_names[:3])
        if len(author_names) > 3:
            first_3 += f" et al. ({len(author_names)} total)"

        published = entry.find(f"{{{ATOM_NS}}}published").text
        abstract = entry.find(f"{{{ATOM_NS}}}summary").text.strip().replace("\n", " ")
        if len(abstract) > 300:
            abstract = abstract[:300] + "..."

        categories = entry.findall(f"{{{ATOM_NS}}}category")
        cat_str = ", ".join(c.get("term") for c in categories)

        # PDF link
        pdf_url = ""
        links = entry.findall(f"{{{ATOM_NS}}}link")
        for link in links:
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break
        if not pdf_url:
            pdf_url = arxiv_id_raw.replace("/abs/", "/pdf/") + ".pdf"

        results.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": first_3,
            "published": published[:10],
            "abstract": abstract,
            "categories": cat_str,
            "pdf_url": pdf_url,
        })
    return results

def main():
    queries = [
        ('"AI agent" OR "autonomous agent"', 1),
        ('"multi-agent" OR "multi agent system"', 2),
        ('"tool use" OR "tool learning" LLM', 3),
        ('"agent planning" OR "agent reasoning"', 4),
        ('"agent memory" OR "MCP" "Model Context Protocol"', 5),
    ]

    total_results = 0
    for query, num in queries:
        print(f"\n{'='*80}")
        print(f"QUERY {num}: {query}")
        print(f"{'='*80}")

        results = search_arxiv(query, max_results=5)
        if not results:
            print("  No results found.")
        else:
            for i, r in enumerate(results, 1):
                print(f"\n--- [{i}] {r['arxiv_id']} ({r['published']}) ---")
                print(f"  Title:    {r['title']}")
                print(f"  Authors:  {r['authors']}")
                print(f"  Abstract: {r['abstract']}")
                print(f"  Cats:     {r['categories']}")
                print(f"  PDF:      {r['pdf_url']}")
            total_results += len(results)

        # 10s delay between queries (not after the last one)
        if num < len(queries):
            print(f"\n  [Waiting 10s before next query...]")
            time.sleep(10)

    print(f"\n{'='*80}")
    print(f"TOTAL: Found {total_results} papers across {len(queries)} queries")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
