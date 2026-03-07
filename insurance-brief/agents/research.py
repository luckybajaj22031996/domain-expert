"""
research.py — Story fetcher for Domain Expert insurance newsletter.

Uses NewsAPI (newsapi.org) to search for India insurance news.
Free tier: 100 requests/day — well within daily usage.

Note: NewsAPI indexes Indian news sources with a ~24-48h delay, so we
search the last 48 hours to reliably capture yesterday's stories.

Queries (targeted for India insurance):
  - "IRDAI"
  - "insurance premium India"
  - "health insurance India claims"
  - "LIC life insurance India"

Returns up to 8 stories as a list of dicts:
  {title, summary, url, source, published_at}
"""

import logging
import os
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2/everything"
CUTOFF_HOURS = 48   # 48h to account for NewsAPI's indexing delay for Indian sources
MAX_STORIES = 8

QUERIES = [
    "IRDAI",
    "insurance premium India",
    "health insurance India claims",
    "LIC life insurance India",
]

# Must contain at least one of these keywords (title or description) to be included
RELEVANCE_KEYWORDS = [
    "insurance", "insurer", "insured", "irdai", "lic", "policyholder",
    "premium", "claim", "reinsurance", "underwriting", "actuary",
    "policy", "coverage", "indemnity",
]


def _cutoff_iso() -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_relevant(article: dict) -> bool:
    """Return True if title or description contains an insurance keyword."""
    text = (
        (article.get("title") or "") + " " + (article.get("description") or "")
    ).lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def _fetch_query(client: httpx.Client, api_key: str, query: str) -> list[dict]:
    params = {
        "q": query,
        "from": _cutoff_iso(),
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 10,
        "apiKey": api_key,
    }
    try:
        resp = client.get(NEWSAPI_BASE, params=params, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("NewsAPI request failed for query '%s': %s", query, exc)
        return []

    data = resp.json()
    if data.get("status") != "ok":
        logger.warning("NewsAPI error for query '%s': %s", query, data.get("message", ""))
        return []

    stories = []
    for article in data.get("articles", []):
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()
        if not title or not url or "[Removed]" in title:
            continue
        if not _is_relevant(article):
            continue

        summary = (
            article.get("description") or article.get("content") or ""
        ).strip()
        if " [+" in summary:
            summary = summary[:summary.index(" [+")].strip()

        source_name = (article.get("source") or {}).get("name") or "NewsAPI"

        stories.append({
            "title": title,
            "summary": summary[:500],
            "url": url,
            "source": source_name,
            "published_at": article.get("publishedAt") or "",
        })

    logger.info("Query '%s' → %d relevant articles", query, len(stories))
    return stories


def fetch_all_stories() -> list[dict]:
    """
    Main entry point.

    Runs all queries against NewsAPI, deduplicates by URL,
    filters for relevance, and returns up to MAX_STORIES sorted newest-first.

    Raises:
        EnvironmentError: If NEWSAPI_KEY is not set.
    """
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        raise EnvironmentError("NEWSAPI_KEY is not set in environment / .env file.")

    seen_urls: set = set()
    all_stories: list = []

    with httpx.Client() as client:
        for query in QUERIES:
            for story in _fetch_query(client, api_key, query):
                if story["url"] not in seen_urls:
                    seen_urls.add(story["url"])
                    all_stories.append(story)

    all_stories.sort(key=lambda s: s.get("published_at") or "", reverse=True)

    result = all_stories[:MAX_STORIES]
    logger.info("Total unique relevant stories: %d (returning %d)", len(all_stories), len(result))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    stories = fetch_all_stories()
    print(f"\n{len(stories)} stories found:\n")
    for i, s in enumerate(stories, 1):
        print(f"[{i}] {s['source']} | {s['published_at'][:16]}")
        print(f"    {s['title']}")
        print(f"    {s['summary'][:120]}...")
        print(f"    {s['url']}\n")
