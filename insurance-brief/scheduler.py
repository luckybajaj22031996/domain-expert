"""
scheduler.py — Daily scheduler for the Domain Expert newsletter.

Runs main.py every day at 07:30 and keeps the process alive.

Usage:
    python scheduler.py
"""

import logging
import sys
import time
from pathlib import Path

import schedule
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)


def _run_newsletter() -> None:
    print("\n── Running Domain Expert ──────────────────────")
    try:
        from main import run
        run()
    except Exception as exc:
        print(f"✗ Unhandled error in run(): {exc}")
    _print_next_run()


def _print_next_run() -> None:
    job = schedule.jobs[0] if schedule.jobs else None
    if job and job.next_run:
        print(f"Next run: {job.next_run.strftime('%A %d %B %Y at %H:%M')}")


def main() -> None:
    schedule.every().day.at("07:30").do(_run_newsletter)

    print("Domain Expert scheduler started — will run daily at 7:30am")
    _print_next_run()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
