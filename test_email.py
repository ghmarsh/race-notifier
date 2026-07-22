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
from notify import load_races, build_email_html, send_email, load_recipients


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

    races = load_races()
    today = date.today()

    # Simulate: one race with registration in 3 days
    fake_upcoming_7 = [{"race": races[0], "reg_date": today + timedelta(days=3), "days_until": 3}]

    # Simulate: one race with registration in 10 days
    fake_upcoming_14 = [
        {"race": races[0], "reg_date": today + timedelta(days=3), "days_until": 3},
        {"race": races[1], "reg_date": today + timedelta(days=10), "days_until": 10},
    ]

    # Simulate: one race happening in 12 days
    fake_upcoming_races = [{"race": races[2], "race_date": today + timedelta(days=12), "days_until": 12}]

    # Simulate: a race ~6 months out with no registration date
    six_month_race = None
    for race in races:
        if not race.get("registration_date"):
            six_month_race = race
            break

    fake_reg_reminders = []
    if six_month_race:
        fake_reg_reminders = [{
            "race": six_month_race,
            "race_date": today + timedelta(days=183),
            "months_out": "~6 months",
        }]

    fake_seasonal_reminder = "summer"

    html_body = build_email_html(fake_upcoming_7, fake_upcoming_14, fake_upcoming_races, fake_reg_reminders, today, fake_seasonal_reminder)

    subject = "[TEST] Race Registration Notifier - All Sections"
    send_email(subject, html_body)
    print("\nTest passed! Check your inbox.")


if __name__ == "__main__":
    main()
