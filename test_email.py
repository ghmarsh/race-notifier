"""
Local test script to verify email sending works.

Before running, set environment variables:
  export SENDER_EMAIL=grantsclaude@gmail.com
  export SENDER_PASSWORD=<your-app-password>

Then run:
  python test_email.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notify import load_races, build_email_html, send_email, load_recipients, find_upcoming_races


def main():
    if "SENDER_EMAIL" not in os.environ or "SENDER_PASSWORD" not in os.environ:
        print("ERROR: Set SENDER_EMAIL and SENDER_PASSWORD environment variables first.")
        print("")
        print("  export SENDER_EMAIL=grantsclaude@gmail.com")
        print("  export SENDER_PASSWORD=<your-16-char-app-password>")
        sys.exit(1)

    recipients = load_recipients()
    if not recipients:
        print("ERROR: No recipients found in recipients.txt")
        sys.exit(1)

    print(f"Sender: {os.environ['SENDER_EMAIL']}")
    print(f"Recipients: {', '.join(recipients)}")
    print("")

    # Create fake "upcoming" data using real races to simulate what a real email looks like
    races = load_races()
    today = date.today()

    fake_upcoming_7 = []
    fake_upcoming_14 = []
    fake_upcoming_races = []
    count = 0
    for race in races:
        if count == 0:
            fake_upcoming_7.append({"race": race, "reg_date": today + timedelta(days=3), "days_until": 3})
        elif count == 1:
            fake_upcoming_14.append({"race": race, "reg_date": today + timedelta(days=10), "days_until": 10})
        elif count == 2:
            fake_upcoming_races.append({"race": race, "race_date": today + timedelta(days=18), "days_until": 18})
        if count >= 2:
            break
        count += 1

    unknown_reg_races = [r for r in races if not r.get("registration_date")][:2]

    html_body = build_email_html(fake_upcoming_7, fake_upcoming_14, fake_upcoming_races, unknown_reg_races, today)

    subject = "[TEST] Race Registration Notifier - Email Test"
    send_email(subject, html_body)
    print("\nTest passed! Check your inbox.")


if __name__ == "__main__":
    main()
