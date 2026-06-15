#!/usr/bin/env python3
"""Fetch real-time data from Hacker News and Reddit public APIs.

Reddit connectivity may be blocked in some sandbox environments.
"""

import json
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
REDDIT_BASE = "https://www.reddit.com/r/{}/hot.json?limit={}"

USER_AGENT = "hermes-agent/1.0 (data aggregation script)"
HEADERS = {"User-Agent": USER_AGENT}
HN_TOP_COUNT = 30
REDDIT_SUBS = ["MachineLearning", "artificial", "LangChain"]
REDDIT_LIMIT = 5

OUTPUT_PATH = "aggregated_results.json"


def fetch_hn_item(item_id):
    """Fetch a single HN item."""
    url = HN_ITEM.format(id=item_id)
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        item = r.json()
        if item and item.get("type") == "story":
            return {
                "title": item.get("title", ""),
                "url": item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "by": item.get("by", ""),
                "time": datetime.utcfromtimestamp(item.get("time", 0)).isoformat() + "Z",
                "hn_id": item_id,
            }
    except Exception as e:
        print(f"  Error fetching HN item {item_id}: {e}")
    return None


def fetch_hn_top_stories():
    """Fetch top stories from HN using concurrent requests."""
    print("Fetching HN top story IDs...")
    resp = requests.get(HN_TOP, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    top_ids = resp.json()[:HN_TOP_COUNT]

    stories = []
    print(f"  Fetching {len(top_ids)} HN items concurrently (10 workers)...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_hn_item, iid): iid for iid in top_ids}
        for future in as_completed(futures):
            result = future.result()
            if result:
                stories.append(result)

    stories.sort(key=lambda s: s["score"], reverse=True)
    print(f"  Retrieved {len(stories)} HN stories")
    return stories


def fetch_reddit_hot(subreddit, limit=5):
    """Fetch hot posts from a subreddit."""
    url = REDDIT_BASE.format(subreddit, limit)
    print(f"  Fetching r/{subreddit}...")
    resp = requests.get(url, headers=HEADERS, timeout=8)
    resp.raise_for_status()
    data = resp.json()

    posts = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        posts.append({
            "title": d.get("title", ""),
            "url": d.get("url", f"https://reddit.com{d.get('permalink', '')}"),
            "score": d.get("score", 0),
            "comments": d.get("num_comments", 0),
            "author": d.get("author", ""),
            "subreddit": d.get("subreddit", subreddit),
            "permalink": f"https://reddit.com{d.get('permalink', '')}",
        })
    return posts


def main():
    results = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "hacker_news": {
            "source": HN_TOP,
            "stories": [],
        },
        "reddit": {},
        "errors": [],
    }

    # --- Hacker News ---
    try:
        stories = fetch_hn_top_stories()
        results["hacker_news"]["stories"] = stories
    except Exception as e:
        err = f"HN fetch failed: {e}"
        print(err)
        results["errors"].append(err)

    # --- Reddit ---
    print("\nFetching Reddit hot posts...")
    for sub in REDDIT_SUBS:
        try:
            posts = fetch_reddit_hot(sub, REDDIT_LIMIT)
            results["reddit"][sub] = posts
            print(f"    {len(posts)} posts from r/{sub}")
            time.sleep(1)
        except Exception as e:
            err_msg = f"r/{sub}: {e}"
            print(f"    Error: {err_msg}")
            results["reddit"][sub] = []
            results["errors"].append(err_msg)

    # Summary
    hn_count = len(results["hacker_news"]["stories"])
    reddit_count = sum(len(v) for v in results["reddit"].values())
    total = hn_count + reddit_count

    results["summary"] = {
        "hn_stories_fetched": hn_count,
        "reddit_posts_fetched": reddit_count,
        "reddit_subreddits": REDDIT_SUBS,
        "total_items": total,
    }

    # Write output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Results saved to {OUTPUT_PATH}")
    print(f"  HN stories:   {hn_count}")
    print(f"  Reddit posts: {reddit_count}")
    print(f"  Total:        {total}")
    if results["errors"]:
        print(f"\nErrors ({len(results['errors'])}):")
        for e in results["errors"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
