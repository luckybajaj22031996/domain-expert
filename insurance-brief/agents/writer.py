"""
writer.py — Newsletter writer agent for Domain Expert.

Takes curated stories (from curation.py) and a concept (from concept.py)
and calls Claude to assemble the full daily newsletter as plain text.

Inputs:
  curated_stories : list[dict]  — each has title, curated_summary,
                                   why_it_matters, url, source
  concept         : dict        — has concept_name, what_it_is,
                                   why_pm_should_care, real_example

Returns:
  str — the complete newsletter, plain text, ready to send or render
"""

import logging
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are the writer for a daily insurance intelligence brief called Domain Expert.
Your reader is a senior insurance PM or BA in India — sharp, busy, no time for fluff.
Write in a confident, punchy tone. No generic openers. No filler.
Every sentence should earn its place.

Assemble the newsletter in this exact structure:

TODAY IN 60 SECONDS
One tight paragraph — what matters in insurance today and why. Max 60 words.

TOP STORIES
For each story: headline, 2-line summary, one line on why it matters to a PM.

CONCEPT OF THE DAY
Concept name as heading.
What it is, why PMs should care, one real Indian example.
Max 150 words total.

Keep the whole thing under 400 words. No bullet point overload.
Write like a smart human, not an AI assistant.\
"""


def _build_user_message(curated_stories: list[dict], concept: dict) -> str:
    stories_block = "\n\n".join(
        f"STORY {i + 1}\n"
        f"Title: {s.get('title', '')}\n"
        f"Summary: {s.get('curated_summary', s.get('summary', ''))}\n"
        f"Why it matters: {s.get('why_it_matters', '')}\n"
        f"Source: {s.get('source', '')}  |  {s.get('url', '')}"
        for i, s in enumerate(curated_stories)
    )

    concept_block = (
        f"CONCEPT\n"
        f"Name: {concept.get('concept_name', '')}\n"
        f"What it is: {concept.get('what_it_is', '')}\n"
        f"Why PM should care: {concept.get('why_pm_should_care', '')}\n"
        f"Real example: {concept.get('real_example', '')}"
    )

    return (
        "Here is today's content. Write the Domain Expert newsletter.\n\n"
        f"{stories_block}\n\n"
        f"{concept_block}"
    )


def write_newsletter(curated_stories: list[dict], concept: dict) -> str:
    """
    Main entry point.

    Args:
        curated_stories: List of story dicts from curation.curate_stories().
        concept:         Concept dict from concept.get_concept().

    Returns:
        The complete newsletter as a plain-text string.
    """
    if not curated_stories:
        raise ValueError("curated_stories is empty — nothing to write.")
    if not concept:
        raise ValueError("concept is empty — nothing to write.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in environment / .env file.")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = _build_user_message(curated_stories, concept)

    logger.info(
        "Sending %d stories + concept '%s' to Claude for writing.",
        len(curated_stories),
        concept.get("concept_name", "?"),
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    newsletter = message.content[0].text.strip()
    word_count = len(newsletter.split())
    logger.info("Newsletter written. Word count: ~%d", word_count)

    return newsletter


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Minimal fixture data so this can run without the other agents
    SAMPLE_STORIES = [
        {
            "title": "IRDAI mandates standard cyber insurance product for SMEs by June 2026",
            "curated_summary": (
                "IRDAI has directed all non-life insurers to file a standard cyber product "
                "for SMEs by June 2026, with capped premiums and a minimum sum insured of Rs 1 crore. "
                "This creates a new standardised product category in a largely untapped segment."
            ),
            "why_it_matters": (
                "PMs must fast-track a compliant cyber product for SMEs within a tight timeline, "
                "requiring rapid work on pricing, underwriting, and SME-focused distribution."
            ),
            "source": "IRDAI",
            "url": "https://irdai.gov.in/circular-cyber-sme-2026",
        },
        {
            "title": "Health insurance claims ratio crosses 90% for three consecutive quarters",
            "curated_summary": (
                "Aggregate claims ratios for retail health insurance breached 90% for three straight "
                "quarters through December 2025, drawing regulator scrutiny of pricing models. "
                "Several large insurers have already filed for premium revisions."
            ),
            "why_it_matters": (
                "A sustained 90%+ claims ratio signals structural underpricing, forcing PMs to "
                "reassess product design and actuarial assumptions before regulators intervene."
            ),
            "source": "Business Standard",
            "url": "https://business-standard.com/health-claims-ratio-90pc",
        },
        {
            "title": "Policybazaar ties up with Rajasthan co-operative bank to target rural customers",
            "curated_summary": (
                "Policybazaar signed an MoU with a Rajasthan co-operative bank to push term and "
                "health products through 200 rural branch touchpoints. Aggregators are moving "
                "aggressively into Tier-3 geographies via bancassurance-style tie-ups."
            ),
            "why_it_matters": (
                "PMs need to check if their products are rural-ready on pricing and language, "
                "and consider similar distribution partnerships before ceding the market."
            ),
            "source": "Economic Times",
            "url": "https://economictimes.com/policybazaar-coop-bank",
        },
    ]

    SAMPLE_CONCEPT = {
        "concept_name": "Appointed Actuary",
        "what_it_is": (
            "An Appointed Actuary is a qualified actuary formally designated by an insurer, "
            "as required by IRDAI, to certify that the company holds adequate reserves to meet "
            "all future policyholder obligations. They review premium rates, assess solvency "
            "margins, and sign off on the financial soundness of the insurer's portfolio."
        ),
        "why_pm_should_care": (
            "When you design a new product or change premium structures, the Appointed Actuary "
            "must validate that your pricing assumptions are sound — their approval is a hard "
            "gate in the product launch process. Understanding their concerns helps PMs build "
            "pricing models that can pass actuarial scrutiny."
        ),
        "real_example": (
            "When LIC launched Jeevan Amar, the Appointed Actuary certified that the mortality "
            "assumptions drawn from Indian Assured Lives Mortality tables were adequate to cover "
            "projected claims over a 40-year term, ensuring IRDAI's 150% solvency margin was met."
        ),
    }

    newsletter = write_newsletter(SAMPLE_STORIES, SAMPLE_CONCEPT)
    print("\n" + "=" * 60)
    print(newsletter)
    print("=" * 60)
    print(f"\nWord count: ~{len(newsletter.split())}")
