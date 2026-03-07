"""
main.py — Orchestrator for the Domain Expert insurance newsletter.

Runs all agents in sequence:
  1. research.py  — scrape stories from last 24 h
  2. curation.py  — pick 3-4 best stories via Claude
  3. concept.py   — pick one insurance concept via Claude
  4. writer.py    — write the "Today in 60 Seconds" intro via Claude
  5. email.html   — render Jinja2 HTML template
  6. mailer.py    — send via Gmail SMTP
"""

import logging
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load .env before importing agents (they each call load_dotenv too, but
# doing it here first ensures the vars are present for all of them)
load_dotenv(Path(__file__).parent / ".env", override=True)

# ---------------------------------------------------------------------------
# Logging — INFO to stdout, clean format
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,          # suppress agent-level debug noise
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent imports (after load_dotenv)
# ---------------------------------------------------------------------------
from agents.research import fetch_all_stories        # noqa: E402
from agents.curation import curate_stories           # noqa: E402
from agents.concept import get_concept               # noqa: E402
from agents.writer import write_newsletter           # noqa: E402
from agents.mailer import send_newsletter            # noqa: E402


def _extract_sixty_seconds(newsletter_text: str) -> str:
    """
    Pulls the 'Today in 60 Seconds' paragraph out of writer.py's plain-text output.

    Writer output always starts with a header line like 'TODAY IN 60 SECONDS'
    followed by the paragraph, then 'TOP STORIES'. We grab everything between
    those two markers and strip it down to the paragraph text.
    """
    # Match everything between the 60-seconds header and the next section header
    match = re.search(
        r"TODAY IN 60 SECONDS\s*\n+(.*?)\n+(?:TOP STORIES|---)",
        newsletter_text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # Fallback: return the first non-empty paragraph if pattern doesn't match
    for line in newsletter_text.splitlines():
        line = line.strip()
        if line and not line.upper().startswith("TODAY"):
            return line
    return ""


def _build_template_stories(curated: list[dict]) -> list[dict]:
    """Maps curation.py dicts → template variable names expected by email.html."""
    return [
        {
            "source":          s.get("source", ""),
            "headline":        s.get("title", ""),
            "url":             s.get("url", "#"),
            "summary":         s.get("curated_summary", s.get("summary", "")),
            "why_it_matters":  s.get("why_it_matters", ""),
        }
        for s in curated
    ]


_DEMO_STORIES = [
    {
        "title": "IRDAI mandates standard cyber insurance product for SMEs by June 2026",
        "summary": (
            "IRDAI has directed all non-life insurers to file a standard cyber product "
            "for SMEs by June 2026, with capped premiums and a minimum sum insured of Rs 1 crore."
        ),
        "url": "https://irdai.gov.in",
        "source": "IRDAI",
        "published_at": "2026-03-08T09:00:00+05:30",
    },
    {
        "title": "Health insurance claims ratio crosses 90% for three consecutive quarters",
        "summary": (
            "Aggregate claims ratios for retail health insurance breached 90% for three straight "
            "quarters through December 2025, drawing regulator scrutiny of pricing models."
        ),
        "url": "https://business-standard.com",
        "source": "Business Standard",
        "published_at": "2026-03-08T08:00:00+05:30",
    },
    {
        "title": "Policybazaar ties up with Rajasthan co-operative bank to target rural customers",
        "summary": (
            "Policybazaar signed an MoU with a Rajasthan co-operative bank to push term and "
            "health products through 200 rural branch touchpoints."
        ),
        "url": "https://economictimes.com",
        "source": "Economic Times",
        "published_at": "2026-03-08T07:30:00+05:30",
    },
    {
        "title": "LIC posts 12% rise in new business premium for Q3 FY26",
        "summary": (
            "LIC reported a 12% year-on-year increase in new business premium for Q3 FY26, "
            "driven by growth in non-par savings products and group credit life schemes."
        ),
        "url": "https://economictimes.com",
        "source": "Economic Times",
        "published_at": "2026-03-08T06:00:00+05:30",
    },
    {
        "title": "IRDAI mulls sandbox relaxations for parametric crop insurance pilots",
        "summary": (
            "IRDAI is considering easing sandbox rules to allow faster pilots of parametric "
            "crop insurance products, especially for kharif season coverage."
        ),
        "url": "https://irdai.gov.in",
        "source": "IRDAI",
        "published_at": "2026-03-07T18:00:00+05:30",
    },
]


def run(demo: bool = False) -> None:
    today = date.today()
    date_str = today.strftime("%d %B %Y")

    # ------------------------------------------------------------------
    # Step 1 — Research
    # ------------------------------------------------------------------
    if demo:
        stories = _DEMO_STORIES
        print(f"✓ Research done — {len(stories)} stories found  [DEMO]")
    else:
        try:
            stories = fetch_all_stories()
        except Exception as exc:
            print(f"✗ Research failed: {exc}")
            sys.exit(1)
        print(f"✓ Research done — {len(stories)} stories found")

    # ------------------------------------------------------------------
    # Step 2 — Curation
    # ------------------------------------------------------------------
    if not stories:
        print("✗ No stories to curate — aborting")
        sys.exit(1)
    try:
        curated = curate_stories(stories)
    except Exception as exc:
        print(f"✗ Curation failed: {exc}")
        sys.exit(1)
    print(f"✓ Curation done — {len(curated)} stories selected")

    # ------------------------------------------------------------------
    # Step 3 — Concept of the day
    # ------------------------------------------------------------------
    try:
        concept = get_concept(seed_date=today)
    except Exception as exc:
        print(f"✗ Concept agent failed: {exc}")
        sys.exit(1)
    print(f"✓ Concept done — \"{concept['concept_name']}\"")

    # ------------------------------------------------------------------
    # Step 4 — Writer (for "Today in 60 Seconds" intro)
    # ------------------------------------------------------------------
    try:
        newsletter_text = write_newsletter(curated, concept)
        sixty_seconds = _extract_sixty_seconds(newsletter_text)
    except Exception as exc:
        print(f"✗ Writer failed: {exc}")
        sys.exit(1)
    print("✓ Writer done — intro paragraph ready")

    # ------------------------------------------------------------------
    # Step 5 — Render Jinja2 HTML template
    # ------------------------------------------------------------------
    try:
        templates_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
        template = env.get_template("email.html")
        html = template.render(
            date=date_str,
            sixty_seconds=sixty_seconds,
            stories=_build_template_stories(curated),
            concept_name=concept["concept_name"],
            what_it_is=concept["what_it_is"],
            why_pm_should_care=concept["why_pm_should_care"],
            real_example=concept["real_example"],
        )
    except Exception as exc:
        print(f"✗ Template render failed: {exc}")
        sys.exit(1)
    print("✓ Template rendered — HTML email ready")

    # ------------------------------------------------------------------
    # Step 6 — Send
    # ------------------------------------------------------------------
    try:
        send_newsletter(html, send_date=today)
    except Exception as exc:
        print(f"✗ Mailer failed: {exc}")
        sys.exit(1)

    print("✓ Domain Expert sent successfully")


if __name__ == "__main__":
    run(demo="--demo" in sys.argv)
