"""
concept.py — Daily insurance concept agent for Domain Expert newsletter.

Runs independently (no input from other agents). Calls Claude to surface
one insurance concept worth deep understanding for a PM or BA in India.

Returns a single dict:
  {concept_name, what_it_is, why_pm_should_care, real_example}
"""

import json
import logging
import os
from datetime import date
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are an insurance education agent for product managers and business analysts in India. "
    "Pick one insurance concept that a PM or BA should understand deeply. "
    "Choose from areas like underwriting, claims, distribution, regulation, reinsurance, "
    "product design, or emerging models like embedded insurance or parametric insurance. "
    "Vary the concept daily — don't repeat basics. "
    "Return in this exact format:\n"
    "- Concept name\n"
    "- What it is (2-3 sentences, plain English, no jargon)\n"
    "- Why a PM should care (2 sentences)\n"
    "- One real-world Indian insurance example"
)

RESPONSE_SCHEMA = """\
Return ONLY a JSON object with exactly these keys:
  - "concept_name"       : string, name of the concept (e.g. "Loss Ratio", "Facultative Reinsurance")
  - "what_it_is"         : string, 2-3 sentence plain-English explanation
  - "why_pm_should_care" : string, exactly 2 sentences on PM relevance
  - "real_example"       : string, one concrete Indian insurance example

Output nothing else — no prose, no markdown fences, just the raw JSON object.\
"""


def get_concept(seed_date: Optional[date] = None) -> dict:
    """
    Main entry point. Fetches a daily insurance concept from Claude.

    Args:
        seed_date: Optional date used to nudge Claude toward variety. Defaults
                   to today. Useful for testing with specific dates.

    Returns:
        Dict with keys: concept_name, what_it_is, why_pm_should_care, real_example.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in environment / .env file.")

    client = anthropic.Anthropic(api_key=api_key)

    today = seed_date or date.today()
    user_message = (
        f"Today is {today.strftime('%A, %d %B %Y')} (day {today.timetuple().tm_yday} of the year). "
        "Pick a concept appropriate for today — use the day of year to vary your selection "
        "across the full range of insurance topics over time.\n\n"
        + RESPONSE_SCHEMA
    )

    logger.info("Requesting daily concept from Claude for %s.", today)

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()
    logger.debug("Claude raw response:\n%s", raw)

    try:
        concept = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude response as JSON: %s\nRaw:\n%s", exc, raw)
        raise ValueError(f"Concept agent returned invalid JSON: {exc}") from exc

    # Validate all expected keys are present and non-empty
    required = {"concept_name", "what_it_is", "why_pm_should_care", "real_example"}
    missing = required - concept.keys()
    if missing:
        raise ValueError(f"Concept agent response missing keys: {missing}")
    empty = [k for k in required if not str(concept[k]).strip()]
    if empty:
        raise ValueError(f"Concept agent response has empty values for: {empty}")

    logger.info("Concept received: %s", concept["concept_name"])
    return concept


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    result = get_concept()

    print(f"\n{'─' * 60}")
    print(f"Concept       : {result['concept_name']}")
    print(f"\nWhat it is    : {result['what_it_is']}")
    print(f"\nWhy PM cares  : {result['why_pm_should_care']}")
    print(f"\nReal example  : {result['real_example']}")
    print(f"{'─' * 60}")
