"""
mailer.py — Email delivery agent for Domain Expert newsletter.

Takes the rendered HTML string and sends it via Gmail SMTP.

Inputs:
  html_content : str  — rendered HTML email (from Jinja2 template)

Reads from .env:
  GMAIL_ADDRESS      — sender and recipient (same address)
  GMAIL_APP_PASSWORD — Gmail app password (not your main Gmail password)
  NEWSLETTER_TO      — optional: comma-separated recipient list (defaults to GMAIL_ADDRESS)
  NEWSLETTER_CC      — optional: comma-separated CC list
  NEWSLETTER_BCC     — optional: comma-separated BCC list
"""

import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _parse_address_list(value: Optional[str]) -> list[str]:
    """
    Parses a comma-separated env var into a clean list of email addresses.
    Empty/whitespace-only entries are ignored.
    """
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def send_newsletter(html_content: str, send_date: Optional[date] = None) -> None:
    """
    Sends the rendered newsletter HTML via Gmail SMTP.

    Args:
        html_content: Fully rendered HTML string of the newsletter.
        send_date:    Date used in the subject line. Defaults to today.

    Raises:
        EnvironmentError: If GMAIL_ADDRESS or GMAIL_APP_PASSWORD are not set.
        smtplib.SMTPException: If sending fails.
    """
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_address:
        raise EnvironmentError("GMAIL_ADDRESS is not set in environment / .env file.")
    if not app_password:
        raise EnvironmentError("GMAIL_APP_PASSWORD is not set in environment / .env file.")

    to_addrs = _parse_address_list(os.getenv("NEWSLETTER_TO")) or [gmail_address]
    cc_addrs = _parse_address_list(os.getenv("NEWSLETTER_CC"))
    bcc_addrs = _parse_address_list(os.getenv("NEWSLETTER_BCC"))
    recipients = [*to_addrs, *cc_addrs, *bcc_addrs]

    if not recipients:
        raise EnvironmentError(
            "No recipients resolved. Set NEWSLETTER_TO or ensure GMAIL_ADDRESS is set."
        )

    today = send_date or date.today()
    subject = f"Domain Expert | {today.strftime('%d %B %Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    msg.attach(MIMEText(html_content, "html"))

    logger.info("Connecting to %s:%s as %s", SMTP_HOST, SMTP_PORT, gmail_address)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, recipients, msg.as_string())

    logger.info("Newsletter sent to %s — subject: %s", ", ".join(recipients), subject)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Read HTML from a file path passed as argument, or use minimal fixture
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            html = f.read()
    else:
        html = "<h1>Domain Expert — test send</h1><p>If you see this, mailer.py works.</p>"

    send_newsletter(html)
    print("Done — check your inbox.")
