import json
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def load_races():
    races_path = Path(__file__).parent / "races.json"
    with open(races_path, "r") as f:
        data = json.load(f)
    return data["races"]


def find_upcoming_registrations(races, today, window_days):
    window_end = today + timedelta(days=window_days)
    upcoming = []
    for race in races:
        reg_date_str = race.get("registration_date")
        if not reg_date_str:
            continue
        try:
            reg_date = datetime.strptime(reg_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= reg_date <= window_end:
            days_until = (reg_date - today).days
            upcoming.append({"race": race, "reg_date": reg_date, "days_until": days_until})
    return sorted(upcoming, key=lambda x: x["days_until"])


def find_upcoming_races(races, today, window_days):
    window_end = today + timedelta(days=window_days)
    upcoming = []
    for race in races:
        race_date_str = race.get("race_date")
        if not race_date_str:
            continue
        try:
            race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= race_date <= window_end:
            days_until = (race_date - today).days
            upcoming.append({"race": race, "race_date": race_date, "days_until": days_until})
    return sorted(upcoming, key=lambda x: x["days_until"])


def find_unknown_registration_dates(races):
    unknown = []
    for race in races:
        if not race.get("registration_date"):
            unknown.append(race)
    return unknown


def format_elevation(race):
    elev = race.get("elevation_gain_ft")
    if not elev:
        return race.get("elevation_notes", "N/A")
    if isinstance(elev, dict):
        parts = [f"{dist}: {gain} ft" for dist, gain in elev.items()]
        return ", ".join(parts)
    return f"{elev} ft"


def build_email_html(upcoming_7, upcoming_14, upcoming_races, unknown_reg_races, today):
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h1 {{ color: #1a1a1a; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }}
            h2 {{ color: #2c3e50; margin-top: 30px; }}
            .race-card {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 15px; margin: 12px 0; background: #fafafa; }}
            .race-card.urgent {{ border-left: 4px solid #e74c3c; background: #fef9f9; }}
            .race-card.soon {{ border-left: 4px solid #f39c12; background: #fefcf5; }}
            .race-name {{ font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 8px; }}
            .race-meta {{ font-size: 14px; color: #555; line-height: 1.6; }}
            .race-meta strong {{ color: #333; }}
            .days-badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; color: white; }}
            .days-badge.urgent {{ background: #e74c3c; }}
            .days-badge.soon {{ background: #f39c12; }}
            a {{ color: #3498db; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .warning {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 12px; margin: 12px 0; }}
            .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; font-size: 12px; color: #999; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Race Registration Notifier</h1>
            <p style="color: #666;">Week of {today.strftime('%B %d, %Y')}</p>
    """

    if upcoming_7:
        html += '<h2>Registration Opening This Week (7 days)</h2>'
        for item in upcoming_7:
            race = item["race"]
            days = item["days_until"]
            urgency = "urgent"
            html += f"""
            <div class="race-card {urgency}">
                <div class="race-name">
                    {race['name']}
                    <span class="days-badge {urgency}">{days} day{'s' if days != 1 else ''}</span>
                </div>
                <div class="race-meta">
                    <strong>Registration Opens:</strong> {item['reg_date'].strftime('%B %d, %Y')}<br>
                    <strong>Race Date:</strong> {race.get('race_date', 'TBD')}<br>
                    <strong>Location:</strong> {race.get('city', '')}, {race.get('state_or_country', '')}<br>
                    <strong>Distances:</strong> {', '.join(race.get('distances', []))}<br>
                    <strong>Elevation:</strong> {format_elevation(race)}<br>
                    <strong>Registration Type:</strong> {race.get('registration_type', 'N/A')}<br>
                    <strong>Website:</strong> <a href="{race.get('website', '#')}">{race.get('website', 'N/A')}</a><br>
                    {f"<strong>Notes:</strong> {race.get('notes', '')}" if race.get('notes') else ''}
                </div>
            </div>
            """

    only_14 = [item for item in upcoming_14 if item["days_until"] > 7]
    if only_14:
        html += '<h2>Registration Opening in 8-14 Days</h2>'
        for item in only_14:
            race = item["race"]
            days = item["days_until"]
            html += f"""
            <div class="race-card soon">
                <div class="race-name">
                    {race['name']}
                    <span class="days-badge soon">{days} days</span>
                </div>
                <div class="race-meta">
                    <strong>Registration Opens:</strong> {item['reg_date'].strftime('%B %d, %Y')}<br>
                    <strong>Race Date:</strong> {race.get('race_date', 'TBD')}<br>
                    <strong>Location:</strong> {race.get('city', '')}, {race.get('state_or_country', '')}<br>
                    <strong>Distances:</strong> {', '.join(race.get('distances', []))}<br>
                    <strong>Elevation:</strong> {format_elevation(race)}<br>
                    <strong>Registration Type:</strong> {race.get('registration_type', 'N/A')}<br>
                    <strong>Website:</strong> <a href="{race.get('website', '#')}">{race.get('website', 'N/A')}</a><br>
                    {f"<strong>Notes:</strong> {race.get('notes', '')}" if race.get('notes') else ''}
                </div>
            </div>
            """

    if upcoming_races:
        html += '<h2>Races Coming Up (Next 14 Days)</h2>'
        for item in upcoming_races:
            race = item["race"]
            days = item["days_until"]
            html += f"""
            <div class="race-card">
                <div class="race-name">
                    {race['name']}
                    <span class="days-badge soon">{days} day{'s' if days != 1 else ''}</span>
                </div>
                <div class="race-meta">
                    <strong>Race Date:</strong> {item['race_date'].strftime('%B %d, %Y')}<br>
                    <strong>Location:</strong> {race.get('city', '')}, {race.get('state_or_country', '')}<br>
                    <strong>Distances:</strong> {', '.join(race.get('distances', []))}<br>
                    <strong>Elevation:</strong> {format_elevation(race)}<br>
                    <strong>Website:</strong> <a href="{race.get('website', '#')}">{race.get('website', 'N/A')}</a><br>
                    {f"<strong>Notes:</strong> {race.get('notes', '')}" if race.get('notes') else ''}
                </div>
            </div>
            """

    if unknown_reg_races:
        html += """
        <h2>Races to Watch (Unknown Registration Dates)</h2>
        <div class="warning">
            These races don't have confirmed registration dates. Check their websites regularly.
        </div>
        """
        for race in unknown_reg_races:
            html += f"""
            <div class="race-card">
                <div class="race-name">{race['name']}</div>
                <div class="race-meta">
                    <strong>Race Date:</strong> {race.get('race_date', 'TBD')}<br>
                    <strong>Location:</strong> {race.get('city', '')}, {race.get('state_or_country', '')}<br>
                    <strong>Distances:</strong> {', '.join(race.get('distances', []))}<br>
                    <strong>Website:</strong> <a href="{race.get('website', '#')}">{race.get('website', 'N/A')}</a>
                </div>
            </div>
            """

    if not upcoming_7 and not only_14 and not upcoming_races and not unknown_reg_races:
        html += """
        <p style="color: #666; font-style: italic; margin: 30px 0;">
            No upcoming registrations or races in the next 14 days. You're all clear!
        </p>
        """

    html += """
            <div class="footer">
                <p>This email was generated automatically by RaceNotifier.<br>
                To update your race list, edit races.json in the repository.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def load_recipients():
    recipients_path = Path(__file__).parent / "recipients.txt"
    recipients = []
    with open(recipients_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                recipients.append(line)
    return recipients


def send_email(subject, html_body):
    sender_email = os.environ["SENDER_EMAIL"]
    sender_password = os.environ["SENDER_PASSWORD"]
    recipients = load_recipients()

    if not recipients:
        print("No recipients found in recipients.txt. No email sent.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())

    print(f"Email sent to {len(recipients)} recipient(s): {', '.join(recipients)}")


def main():
    today = datetime.now().date()
    races = load_races()

    upcoming_7 = find_upcoming_registrations(races, today, 7)
    upcoming_14 = find_upcoming_registrations(races, today, 14)
    upcoming_races = find_upcoming_races(races, today, 14)
    unknown_reg_races = find_unknown_registration_dates(races)

    has_content = upcoming_7 or upcoming_14 or upcoming_races or unknown_reg_races

    if not has_content:
        print("No upcoming registrations or races. No email sent.")
        return

    html_body = build_email_html(upcoming_7, upcoming_14, upcoming_races, unknown_reg_races, today)

    if upcoming_7:
        subject = f"🏃 Race Alert: {len(upcoming_7)} registration(s) opening THIS WEEK!"
    elif upcoming_14:
        only_14 = [item for item in upcoming_14 if item["days_until"] > 7]
        subject = f"🏃 Race Alert: {len(only_14)} registration(s) opening in 8-14 days"
    elif upcoming_races:
        subject = f"🏃 Race Alert: {len(upcoming_races)} race(s) coming up in the next 14 days"
    else:
        subject = "🏃 Race Alert: Races to watch (unknown registration dates)"

    send_email(subject, html_body)
    print(f"Notified about {len(upcoming_14)} registration(s), {len(upcoming_races)} upcoming race(s), and {len(unknown_reg_races)} unknown-date race(s).")


if __name__ == "__main__":
    main()
