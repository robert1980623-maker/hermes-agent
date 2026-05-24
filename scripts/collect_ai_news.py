#!/usr/bin/env python3
"""
AI/ML Daily News Collector
==========================
Collects today's AI/ML community discussions from:
1. Reddit (r/MachineLearning, r/artificial, r/LangChain)
2. OpenAI, Anthropic, Google AI blogs
3. GitHub trending AI/Agent repos
4. X/Twitter trending topics (#AI #Agent #LLM)

Usage:
    python collect_ai_news.py [--date 2026-05-14] [--output report.md]

Requires: requests, beautifulsoup4
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages: requests, beautifulsoup4")
    print("Install with: pip install requests beautifulsoup4")
    sys.exit(1)


# ─── Configuration ───────────────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


# ─── Reddit Collector ────────────────────────────────────────────────────────

def collect_reddit(subreddit: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Collect hot posts from a subreddit via Reddit's JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        posts = []
        for item in data.get("data", {}).get("children", []):
            post = item.get("data", {})
            created_utc = post.get("created_utc", 0)
            created_date = datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%d")
            
            posts.append({
                "source": f"r/{subreddit}",
                "title": post.get("title", ""),
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "author": post.get("author", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "created_utc": created_utc,
                "created_date": created_date,
                "selftext": (post.get("selftext", "") or "")[:500],
                "link_flair_text": post.get("link_flair_text", ""),
                "domain": post.get("domain", ""),
                "technical_substance": _assess_reddit_substance(post),
            })
        return posts
    except Exception as e:
        print(f"  ❌ Error collecting r/{subreddit}: {e}")
        return []


def _assess_reddit_substance(post: Dict) -> str:
    """Heuristic assessment of technical substance."""
    title = (post.get("title", "") or "").lower()
    selftext = (post.get("selftext", "") or "").lower()
    domain = (post.get("domain", "") or "").lower()
    
    substance_keywords = [
        "paper", "benchmark", "evaluation", "architecture", "training",
        "fine-tune", "quantization", "attention", "moe", "router",
        "agent", "tool use", "function calling", "rag", "retrieval",
        "embedding", "tokenizer", "loss", "gradient", "optimizer",
        "inference", "throughput", "latency", "memory", "gpu",
    ]
    hype_keywords = ["amazing", "incredible", "game-changer", "revolutionary", "hype"]
    
    text = title + " " + selftext
    substance_count = sum(1 for kw in substance_keywords if kw in text)
    hype_count = sum(1 for kw in hype_keywords if kw in text)
    
    if substance_count >= 3 and hype_count <= 1:
        return "high"
    elif substance_count >= 1:
        return "medium"
    elif domain in ["arxiv.org", "github.com", "openai.com", "anthropic.com"]:
        return "high"
    return "low"


# ─── Blog Collectors ─────────────────────────────────────────────────────────

def collect_openai_blog() -> List[Dict[str, Any]]:
    """Scrape recent posts from OpenAI blog."""
    url = "https://openai.com/blog/"
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = []
        
        # OpenAI blog uses specific card elements
        for article in soup.find_all("article")[:15]:
            title_el = article.find(["h2", "h3"]) or article.find("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.find("a") or title_el
            href = link.get("href", "") if isinstance(link, object) else ""
            if not href.startswith("http"):
                href = f"https://openai.com{href}"
            
            date_el = article.find("time")
            date_text = date_el.get_text(strip=True) if date_el else ""
            
            excerpt_el = article.find("p")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            
            posts.append({
                "source": "OpenAI Blog",
                "title": title,
                "url": href,
                "date": date_text,
                "excerpt": excerpt[:300],
                "technical_substance": "high" if any(
                    kw in title.lower() for kw in ["model", "api", "research", "gpt", "embedding", "training"]
                ) else "medium",
            })
        return posts
    except Exception as e:
        print(f"  ❌ Error collecting OpenAI blog: {e}")
        return []


def collect_anthropic_blog() -> List[Dict[str, Any]]:
    """Scrape recent posts from Anthropic news/blog."""
    url = "https://www.anthropic.com/news"
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = []
        
        for article in soup.find_all("article")[:15]:
            title_el = article.find(["h2", "h3"]) or article.find("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.find("a") or title_el
            href = link.get("href", "") if isinstance(link, object) else ""
            if not href.startswith("http"):
                href = f"https://www.anthropic.com{href}"
            
            date_el = article.find("time")
            date_text = date_el.get_text(strip=True) if date_el else ""
            
            excerpt_el = article.find("p")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            
            posts.append({
                "source": "Anthropic Blog",
                "title": title,
                "url": href,
                "date": date_text,
                "excerpt": excerpt[:300],
                "technical_substance": "high",  # Anthropic blog is typically substantive
            })
        return posts
    except Exception as e:
        print(f"  ❌ Error collecting Anthropic blog: {e}")
        return []


def collect_google_ai_blog() -> List[Dict[str, Any]]:
    """Scrape recent posts from Google AI blog."""
    url = "https://blog.google/technology/ai/"
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = []
        
        for article in soup.find_all("article")[:15]:
            title_el = article.find(["h2", "h3"]) or article.find("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.find("a") or title_el
            href = link.get("href", "") if isinstance(link, object) else ""
            if not href.startswith("http"):
                href = f"https://blog.google{href}"
            
            date_el = article.find("time")
            date_text = date_el.get_text(strip=True) if date_el else ""
            
            excerpt_el = article.find("p")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            
            posts.append({
                "source": "Google AI Blog",
                "title": title,
                "url": href,
                "date": date_text,
                "excerpt": excerpt[:300],
                "technical_substance": "high" if any(
                    kw in title.lower() for kw in ["gemini", "transformer", "research", "model", "pa"]
                ) else "medium",
            })
        return posts
    except Exception as e:
        print(f"  ❌ Error collecting Google AI blog: {e}")
        return []


# ─── GitHub Trending Collector ───────────────────────────────────────────────

def collect_github_trending(since: str = "daily") -> List[Dict[str, Any]]:
    """Scrape GitHub trending repositories for AI/Agent topics."""
    url = f"https://github.com/trending?since={since}"
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        repos = []
        
        for article in soup.find_all("article", class_="Box-row")[:30]:
            # Repo name
            h2 = article.find("h2")
            if not h2:
                continue
            repo_link = h2.find("a")
            if not repo_link:
                continue
            repo_name = repo_link.get_text(strip=True)
            repo_url = f"https://github.com{repo_link.get('href', '')}"
            
            # Description
            p = article.find("p", class_="col-9")
            description = p.get_text(strip=True) if p else ""
            
            # Language
            lang_el = article.find("span", itemprop="programmingLanguage")
            language = lang_el.get_text(strip=True) if lang_el else ""
            
            # Stars
            stars_el = article.find("a", href=lambda h: h and "/stargazers" in h)
            stars_text = stars_el.get_text(strip=True) if stars_el else ""
            
            # Today's stars
            today_stars_el = article.find("span", class_="d-inline-block", string=lambda t: t and "today" in t)
            today_stars = ""
            if not today_stars_el:
                # Alternative selector
                for span in article.find_all("span", class_="d-inline-block"):
                    text = span.get_text(strip=True)
                    if "today" in text.lower():
                        today_stars = text
                        break
            
            # Check if AI/Agent related
            is_ai_related = any(
                kw in (repo_name + description).lower()
                for kw in ["ai", "agent", "llm", "ml", "machine-learning", "gpt", 
                          "transformer", "chatbot", "nlp", "deep-learning", "mcp",
                          "rag", "embedding", "inference", "model", "llama"]
            )
            
            if is_ai_related:
                repos.append({
                    "source": "GitHub Trending",
                    "repo": repo_name,
                    "url": repo_url,
                    "description": description[:200],
                    "language": language,
                    "total_stars": stars_text,
                    "today_stars": today_stars,
                    "technical_substance": _assess_github_substance(repo_name, description),
                })
        return repos
    except Exception as e:
        print(f"  ❌ Error collecting GitHub trending: {e}")
        return []


def _assess_github_substance(repo_name: str, description: str) -> str:
    """Heuristic assessment of GitHub repo technical substance."""
    text = (repo_name + description).lower()
    substance_indicators = [
        "framework", "library", "benchmark", "implementation", "runtime",
        "compiler", "inference", "quantization", "training", "distributed",
        "agent", "tool-use", "mcp", "function-calling", "memory",
    ]
    count = sum(1 for kw in substance_indicators if kw in text)
    if count >= 2:
        return "high"
    elif count >= 1:
        return "medium"
    return "low"


# ─── X/Twitter Collector ─────────────────────────────────────────────────────

def collect_x_trending_topics() -> List[Dict[str, Any]]:
    """
    Collect trending topics from X/Twitter for AI/Agent/LLM hashtags.
    Note: X has aggressive rate limiting and anti-scraping measures.
    This uses Nitter instances as a fallback.
    """
    results = []
    
    # Try Nitter instances for hashtag searches
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
    ]
    
    hashtags = ["AI", "Agent", "LLM"]
    
    for instance in nitter_instances:
        for tag in hashtags:
            url = f"{instance}/search?q=%23{tag}&f=tweets"
            try:
                resp = SESSION.get(url, timeout=15)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    tweets = soup.find_all("div", class_="tweet-body")
                    for tweet in tweets[:10]:
                        content_el = tweet.find("div", class_="tweet-content")
                        if content_el:
                            content = content_el.get_text(strip=True)
                            results.append({
                                "source": f"X/Twitter (#{tag})",
                                "content": content[:280],
                                "nitter_url": url,
                            })
                    if results:
                        break  # Found results, stop trying instances
            except Exception:
                continue
        if results:
            break
    
    if not results:
        print("  ⚠️  Could not collect X/Twitter trending (rate limiting or instances down)")
    
    return results


# ─── Report Generation ───────────────────────────────────────────────────────

def generate_report(
    date: str,
    reddit_posts: Dict[str, List[Dict]],
    blog_posts: Dict[str, List[Dict]],
    github_repos: List[Dict],
    twitter_topics: List[Dict],
    output_file: str = None,
) -> str:
    """Generate a markdown report from collected data."""
    
    lines = [
        f"# AI/ML Community Discussions — Daily Report",
        f"## Date: {date}",
        f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"",
        "---",
        f"",
    ]
    
    # ── Reddit Section ──
    lines.append("## 1. Reddit Hot Posts\n")
    for subreddit, posts in reddit_posts.items():
        lines.append(f"### r/{subreddit}\n")
        today_posts = [p for p in posts if p.get("created_date") == date]
        if not today_posts:
            today_posts = posts[:10]  # Show recent if no exact date match
            lines.append(f"*No posts from exact date {date}; showing recent hot posts*\n")
        
        for i, post in enumerate(today_posts[:15], 1):
            lines.append(f"**{i}. {post['title']}**")
            lines.append(f"   - Score: {post['score']} | Comments: {post['num_comments']} | Ratio: {post['upvote_ratio']:.0%}")
            lines.append(f"   - Author: {post['author']} | Flair: {post.get('link_flair_text', 'N/A')}")
            lines.append(f"   - Substance: {post['technical_substance'].upper()}")
            lines.append(f"   - URL: {post['url']}")
            if post.get("selftext"):
                preview = post["selftext"][:200].replace("\n", " ")
                lines.append(f"   - Preview: {preview}...")
            lines.append("")
    
    # ── Blog Posts Section ──
    lines.append("## 2. Major AI Lab Blog Posts\n")
    for source_name, posts in blog_posts.items():
        lines.append(f"### {source_name}\n")
        if not posts:
            lines.append("*No recent posts found or collection failed*\n")
            continue
        for i, post in enumerate(posts[:10], 1):
            lines.append(f"**{i}. {post['title']}**")
            lines.append(f"   - Date: {post.get('date', 'N/A')} | Substance: {post['technical_substance'].upper()}")
            lines.append(f"   - URL: {post['url']}")
            if post.get("excerpt"):
                lines.append(f"   - Excerpt: {post['excerpt'][:200]}...")
            lines.append("")
    
    # ── GitHub Trending Section ──
    lines.append("## 3. GitHub Trending AI/Agent Repos\n")
    if not github_repos:
        lines.append("*No AI-related repos found or collection failed*\n")
    else:
        for i, repo in enumerate(github_repos[:20], 1):
            lines.append(f"**{i}. [{repo['repo']}]({repo['url']})**")
            lines.append(f"   - Description: {repo['description']}")
            lines.append(f"   - Language: {repo['language']} | Stars: {repo['total_stars']} | Today: {repo.get('today_stars', 'N/A')}")
            lines.append(f"   - Substance: {repo['technical_substance'].upper()}")
            lines.append("")
    
    # ── X/Twitter Section ──
    lines.append("## 4. X/Twitter Trending Topics (#AI #Agent #LLM)\n")
    if not twitter_topics:
        lines.append("*Could not collect X/Twitter data (rate limiting or access issues)*\n")
    else:
        seen = set()
        for tweet in twitter_topics[:20]:
            if tweet["content"] not in seen:
                seen.add(tweet["content"])
                lines.append(f"- **{tweet['source']}**: {tweet['content'][:200]}")
        lines.append("")
    
    # ── Summary Section ──
    lines.append("---\n")
    lines.append("## Summary & Sentiment Analysis\n")
    
    # Count substances
    all_reddit = [p for posts in reddit_posts.values() for p in posts]
    all_items = all_reddit + [p for posts in blog_posts.values() for p in posts] + github_repos
    
    high = sum(1 for x in all_items if x.get("technical_substance") == "high")
    medium = sum(1 for x in all_items if x.get("technical_substance") == "medium")
    low = sum(1 for x in all_items if x.get("technical_substance") == "low")
    
    lines.append(f"- **High substance items**: {high}")
    lines.append(f"- **Medium substance items**: {medium}")
    lines.append(f"- **Low substance items**: {low}")
    lines.append(f"- **Total Reddit posts collected**: {sum(len(v) for v in reddit_posts.values())}")
    lines.append(f"- **Total blog posts collected**: {sum(len(v) for v in blog_posts.values())}")
    lines.append(f"- **Total GitHub repos collected**: {len(github_repos)}")
    lines.append(f"- **Total X/Twitter items collected**: {len(twitter_topics)}")
    lines.append("")
    
    report = "\n".join(lines)
    
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✅ Report saved to: {output_file}")
    
    return report


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    date = datetime.now().strftime("%Y-%m-%d")
    output_file = None
    
    # Parse simple CLI args
    for i, arg in enumerate(sys.argv):
        if arg == "--date" and i + 1 < len(sys.argv):
            date = sys.argv[i + 1]
        elif arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
    
    if not output_file:
        output_file = f"ai_news_report_{date}.md"
    
    print(f"🔍 Collecting AI/ML news for {date}...\n")
    
    # 1. Reddit
    print("📊 Collecting Reddit posts...")
    reddit_subreddits = ["MachineLearning", "artificial", "LangChain"]
    reddit_posts = {}
    for sub in reddit_subreddits:
        print(f"  Fetching r/{sub}...")
        reddit_posts[sub] = collect_reddit(sub)
        print(f"  → {len(reddit_posts[sub])} posts collected")
    
    # 2. Blog posts
    print("\n📝 Collecting blog posts...")
    blog_posts = {}
    
    print("  Fetching OpenAI Blog...")
    blog_posts["OpenAI Blog"] = collect_openai_blog()
    print(f"  → {len(blog_posts['OpenAI Blog'])} posts")
    
    print("  Fetching Anthropic Blog...")
    blog_posts["Anthropic Blog"] = collect_anthropic_blog()
    print(f"  → {len(blog_posts['Anthropic Blog'])} posts")
    
    print("  Fetching Google AI Blog...")
    blog_posts["Google AI Blog"] = collect_google_ai_blog()
    print(f"  → {len(blog_posts['Google AI Blog'])} posts")
    
    # 3. GitHub trending
    print("\n⭐ Collecting GitHub trending repos...")
    github_repos = collect_github_trending("daily")
    print(f"  → {len(github_repos)} AI-related repos")
    
    # 4. X/Twitter
    print("\n🐦 Collecting X/Twitter trending topics...")
    twitter_topics = collect_x_trending_topics()
    print(f"  → {len(twitter_topics)} items")
    
    # Generate report
    print(f"\n📋 Generating report...")
    report = generate_report(date, reddit_posts, blog_posts, github_repos, twitter_topics, output_file)
    
    # Also save JSON for programmatic use
    json_data = {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "reddit": {k: v for k, v in reddit_posts.items()},
        "blogs": {k: v for k, v in blog_posts.items()},
        "github_trending": github_repos,
        "twitter_topics": twitter_topics,
    }
    json_file = output_file.replace(".md", ".json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"✅ JSON data saved to: {json_file}")
    
    print(f"\n{'='*60}")
    print(f"Collection complete!")
    print(f"  Report: {output_file}")
    print(f"  JSON:   {json_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
