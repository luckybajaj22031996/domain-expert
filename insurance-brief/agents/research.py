"""
research.py — Story scraper for Domain Expert insurance newsletter.

Fetches stories from the last 24 hours from three sources:
  - IRDAI (official regulatory body RSS)
  - Economic Times insurance section
  - Business Standard insurance section

Returns a list of Story dicts: {title, summary, url, source}
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CUTOFF_HOURS = 24

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DomainExpertBot/1.0; +https://github.com/yourusername/domain-expert)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SOURCES = {
    "IRDAI": {
        "url": "https://irdai.gov.in/latest-updates",   # HTML — no RSS; scraped directly
        "type": "irdai_html",
    },
    "Economic Times": {
        "url": "https://economictimes.indiatimes.com/industry/banking/insurance/rssfeeds/13358575.cms",
        "type": "rss",
    },
    "Business Standard": {
        "url": "https://www.business-standard.com/rss/finance/insurance-2302.rss",
        "type": "rss",
    },
}


@dataclass
class Story:
    title: str
    summary: str
    url: str
    source: str
    published_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


def _cutoff_time() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)


def _is_recent(pub_date: Optional[datetime], cutoff: datetime) -> bool:
    """Return True if pub_date is within the cutoff window, or if date is unknown."""
    if pub_date is None:
        return True  # include when date unavailable; caller can filter later
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    return pub_date >= cutoff


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RFC 2822 date string (standard in RSS) to aware datetime."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# RSS parser (used by ET and BS)
# ---------------------------------------------------------------------------

def _fetch_rss(client: httpx.Client, url: str, source_name: str) -> list[Story]:
    """Generic RSS/Atom feed parser. Returns Story objects."""
    try:
        response = client.get(url, timeout=15)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch RSS for %s: %s", source_name, exc)
        return []

    cutoff = _cutoff_time()
    stories: list[Story] = []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        logger.warning("XML parse error for %s: %s", source_name, exc)
        return []

    # Handle both RSS <channel><item> and Atom <entry>
    items = root.findall(".//item") or root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    )

    for item in items:
        title_el = item.find("title") or item.find(
            "{http://www.w3.org/2005/Atom}title"
        )
        link_el = item.find("link") or item.find(
            "{http://www.w3.org/2005/Atom}link"
        )
        desc_el = item.find("description") or item.find(
            "{http://www.w3.org/2005/Atom}summary"
        )
        date_el = item.find("pubDate") or item.find(
            "{http://www.w3.org/2005/Atom}updated"
        )

        title = (title_el.text or "").strip() if title_el is not None else ""
        # RSS <link> can be text or an href attribute (Atom)
        if link_el is not None:
            url_val = (link_el.text or link_el.get("href", "")).strip()
        else:
            url_val = ""
        summary_raw = (desc_el.text or "").strip() if desc_el is not None else ""
        pub_date = _parse_rss_date(date_el.text) if date_el is not None else None

        if not title or not url_val:
            continue

        if not _is_recent(pub_date, cutoff):
            continue

        # Strip HTML tags that sometimes appear in RSS descriptions
        summary = BeautifulSoup(summary_raw, "html.parser").get_text(separator=" ").strip()
        summary = " ".join(summary.split())  # normalise whitespace

        stories.append(
            Story(
                title=title,
                summary=summary[:500],  # cap length
                url=url_val,
                source=source_name,
                published_at=pub_date,
            )
        )

    logger.info("Fetched %d recent stories from %s", len(stories), source_name)
    return stories


# ---------------------------------------------------------------------------
# IRDAI HTML scraper (no public RSS available)
# ---------------------------------------------------------------------------

def _fetch_irdai(client: httpx.Client) -> list[Story]:
    """
    Scrapes IRDAI latest-updates page.
    The page lists circulars/notifications in a table with date, title, and PDF link.
    """
    url = SOURCES["IRDAI"]["url"]
    source_name = "IRDAI"

    try:
        response = client.get(url, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch IRDAI page: %s", exc)
        return []

    cutoff = _cutoff_time()
    soup = BeautifulSoup(response.text, "html.parser")
    stories: list[Story] = []

    # IRDAI renders updates in a <table> — rows have date + title + link
    rows = soup.select("table tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue

        # Attempt to find date in first or last column
        date_text = ""
        link_tag = None
        title = ""

        for col in cols:
            a = col.find("a")
            if a and a.get_text(strip=True):
                link_tag = a
                title = a.get_text(strip=True)
            else:
                candidate = col.get_text(strip=True)
                # Simple heuristic: date columns are short and contain digits
                if len(candidate) <= 20 and any(ch.isdigit() for ch in candidate):
                    date_text = candidate

        if not title or not link_tag:
            continue

        href = link_tag.get("href", "")
        if href and not href.startswith("http"):
            href = "https://irdai.gov.in" + href

        # Try to parse date formats like "07-03-2026" or "March 07, 2026"
        pub_date: Optional[datetime] = None
        for fmt in ("%d-%m-%Y", "%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                pub_date = datetime.strptime(date_text, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

        if not _is_recent(pub_date, cutoff):
            continue

        stories.append(
            Story(
                title=title,
                summary=f"IRDAI regulatory update: {title}",
                url=href,
                source=source_name,
                published_at=pub_date,
            )
        )

    logger.info("Fetched %d recent stories from %s", len(stories), source_name)
    return stories


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_all_stories() -> list[dict]:
    """
    Main entry point.

    Fetches stories from all configured sources in a single synchronous session
    (httpx client with connection reuse). Returns a list of story dicts sorted
    newest-first.
    """
    all_stories: list[Story] = []

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        # RSS sources
        for source_name, config in SOURCES.items():
            if config["type"] == "rss":
                all_stories.extend(_fetch_rss(client, config["url"], source_name))
            elif config["type"] == "irdai_html":
                all_stories.extend(_fetch_irdai(client))

    # Sort newest first; stories with unknown dates go last
    all_stories.sort(
        key=lambda s: s.published_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    logger.info("Total stories fetched across all sources: %d", len(all_stories))
    return [s.to_dict() for s in all_stories]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    stories = fetch_all_stories()
    for i, s in enumerate(stories, 1):
        print(f"\n[{i}] {s['source']} | {s['published_at'] or 'date unknown'}")
        print(f"    {s['title']}")
        print(f"    {s['summary'][:120]}...")
        print(f"    {s['url']}")
