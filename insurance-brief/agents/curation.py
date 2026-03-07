"""
curation.py — Story curation agent for Domain Expert insurance newsletter.

Takes the raw list of stories from research.py and uses Claude to select
the 3-4 most relevant stories for a senior insurance PM in India.

Returns a list of curated story dicts:
  {title, summary, url, source, published_at, curated_summary, why_it_matters}
"""

import json
import logging
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are a curation agent for a senior insurance PM in India. "
    "From these stories, pick the 3-4 most relevant to product strategy, "
    "regulation, or market shifts. Ignore press releases, fluff, and "
    "generic business news. For each picked story, write a 2-line summary "
    "and one line on why it matters to an insurance PM."
)

RESPONSE_SCHEMA = """\
Return ONLY a JSON array. Each element must have exactly these keys:
  - "index"          : integer, 0-based index of the story in the input list
  - "curated_summary": string, exactly 2 sentences summarising the story
  - "why_it_matters" : string, exactly 1 sentence on why an insurance PM should care

Example:
[
  {
    "index": 2,
    "curated_summary": "IRDAI has mandated insurers to launch a standard health product by Q3. The move aims to improve penetration in Tier-2 and Tier-3 cities.",
    "why_it_matters": "PMs will need to fast-track a compliant product variant and rethink distribution for underserved geographies."
  }
]

Output nothing else — no prose, no markdown fences, just the raw JSON array.\
"""


def _build_user_message(stories: list[dict]) -> str:
    lines = []
    for i, s in enumerate(stories):
        lines.append(
            f"[{i}] {s.get('source', '')} | {s.get('published_at', 'date unknown')}\n"
            f"Title: {s.get('title', '')}\n"
            f"Summary: {s.get('summary', '')}\n"
            f"URL: {s.get('url', '')}"
        )
    return "\n\n".join(lines)


def curate_stories(stories: list[dict]) -> list[dict]:
    """
    Main entry point.

    Args:
        stories: Raw story dicts as returned by research.fetch_all_stories().

    Returns:
        A subset of those dicts (3-4 items) enriched with:
          - curated_summary: 2-sentence Claude-written summary
          - why_it_matters:  1-sentence relevance note for an insurance PM
    """
    if not stories:
        logger.warning("No stories passed to curation agent; returning empty list.")
        return []

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in environment / .env file.")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = _build_user_message(stories) + "\n\n" + RESPONSE_SCHEMA

    logger.info("Sending %d stories to Claude for curation.", len(stories))

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()
    logger.debug("Claude raw response:\n%s", raw)

    try:
        picks = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude response as JSON: %s\nRaw:\n%s", exc, raw)
        raise ValueError(f"Curation agent returned invalid JSON: {exc}") from exc

    curated: list[dict] = []
    for pick in picks:
        idx = pick.get("index")
        if idx is None or not (0 <= idx < len(stories)):
            logger.warning("Claude returned out-of-range index %s — skipping.", idx)
            continue
        story = dict(stories[idx])  # copy so we don't mutate the input
        story["curated_summary"] = pick.get("curated_summary", "")
        story["why_it_matters"] = pick.get("why_it_matters", "")
        curated.append(story)

    logger.info("Curation complete: %d stories selected.", len(curated))
    return curated


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1]))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from agents.research import fetch_all_stories

    raw_stories = fetch_all_stories()
    print(f"\nFetched {len(raw_stories)} raw stories. Running curation...\n")

    results = curate_stories(raw_stories)

    for i, s in enumerate(results, 1):
        print(f"{'─' * 60}")
        print(f"[{i}] {s['source']}  |  {s.get('published_at', 'n/a')}")
        print(f"Title   : {s['title']}")
        print(f"Summary : {s['curated_summary']}")
        print(f"Why PM  : {s['why_it_matters']}")
        print(f"URL     : {s['url']}")
    print(f"{'─' * 60}")
