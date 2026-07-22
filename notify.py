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


def resolve_date(mm_dd_str, today):
    """Convert MM-DD string to a full date. Uses this year if the date hasn't
    passed yet, otherwise next year."""
    try:
        month, day = map(int, mm_dd_str.split("-"))
    except (ValueError, AttributeError):
        return None
    from datetime import date
    this_year = date(today.year, month, day)
    if this_year >= today:
        return this_year
    return date(today.year + 1, month, day)


def find_upcoming_registrations(races, today, window_days):
    window_end = today + timedelta(days=window_days)
    upcoming = []
    for race in races:
        reg_date_str = race.get("registration_date")
        if not reg_date_str:
            continue
        reg_date = resolve_date(reg_date_str, today)
        if not reg_date:
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
        race_date = resolve_date(race_date_str, today)
        if not race_date:
            continue
        if today <= race_date <= window_end:
            days_until = (race_date - today).days
            upcoming.append({"race": race, "race_date": race_date, "days_until": days_until})
    return sorted(upcoming, key=lambda x: x["days_until"])


def find_unknown_reg_reminders(races, today):
    """For races without a known registration date, remind at ~9 months and
    ~6 months before the race date (within a 7-day window so it triggers
    once per reminder period on the weekly email)."""
    reminders = []
    for race in races:
        if race.get("registration_date"):
            continue
        race_date_str = race.get("race_date")
        if not race_date_str:
            continue
        race_date = resolve_date(race_date_str, today)
        if not race_date:
            continue
        days_until_race = (race_date - today).days
        if days_until_race < 0:
            continue
        # 9 months = ~274 days, 6 months = ~183 days, 3 months = ~91 days
        # Trigger if within a 7-day window of these milestones
        for months, label in [(9, "~9 months"), (6, "~6 months"), (3, "~3 months")]:
            target_days = months * 30.44  # average days per month
            if abs(days_until_race - target_days) <= 7:
                reminders.append({"race": race, "race_date": race_date, "months_out": label})
                break
    return reminders


def check_seasonal_update_reminder(today):
    """Return a reminder string if this is the week closest to June 1 or January 1.
    The cron runs weekly on Mondays, so we trigger if today is within 3 days of
    those dates (covers the Monday nearest to each)."""
    from datetime import date
    jun1 = date(today.year, 6, 1)
    jan1 = date(today.year, 1, 1)
    jan1_next = date(today.year + 1, 1, 1)

    closest_jan = jan1 if abs((today - jan1).days) <= abs((today - jan1_next).days) else jan1_next
    if abs((today - jun1).days) <= 3:
        return "summer"
    if abs((today - closest_jan).days) <= 3:
        return "winter"
    return None


def format_elevation(race):
    elev = race.get("elevation_gain_ft")
    if not elev:
        return race.get("elevation_notes", "N/A")
    if isinstance(elev, dict):
        parts = [f"{dist}: {gain} ft" for dist, gain in elev.items()]
        return ", ".join(parts)
    return f"{elev} ft"


def build_email_html(upcoming_7, upcoming_14, upcoming_races, reg_reminders, today, seasonal_reminder=None):
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h1 {{ color: #1a1a1a; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }}
            h2 {{ color: #2c3e50; margin-top: 30px; }}
            .race-card {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin: 12px 0; background: #fafafa; }}
            .race-card.urgent {{ border-left: 4px solid #e74c3c; background: #fef9f9; }}
            .race-card.soon {{ border-left: 4px solid #f39c12; background: #fefcf5; }}
            .tier1 {{ margin-bottom: 10px; }}
            .race-name {{ font-size: 20px; font-weight: 700; color: #2c3e50; }}
            .race-name a {{ color: #2c3e50; text-decoration: none; }}
            .days-badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; color: white; vertical-align: middle; }}
            .days-badge.urgent {{ background: #e74c3c; }}
            .days-badge.soon {{ background: #f39c12; }}
            .tier2 {{ margin-bottom: 10px; }}
            .tier2 table {{ border-collapse: collapse; }}
            .tier2 td {{ padding: 0 20px 0 0; vertical-align: top; }}
            .date-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; color: #888; font-weight: 600; }}
            .date-value {{ font-size: 15px; color: #333; font-weight: 500; }}
            .reg-type {{ display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
            .reg-type-lottery {{ background: #fff3e0; color: #e65100; }}
            .reg-type-direct {{ background: #e8f5e9; color: #2e7d32; }}
            .tier3 {{ font-size: 13px; color: #666; line-height: 1.6; }}
            .tier3 .label {{ font-weight: 600; color: #555; font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; }}
            .notes {{ margin-top: 8px; font-size: 12px; color: #888; font-style: italic; border-top: 1px solid #f0f0f0; padding-top: 6px; }}
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

    def format_race_date(race):
        rd = race.get('race_date')
        if not rd:
            return 'TBD'
        resolved = resolve_date(rd, today)
        return resolved.strftime('%B %d, %Y') if resolved else 'TBD'

    def render_reg_card(item, urgency):
        race = item["race"]
        days = item["days_until"]
        reg_type_class = f"reg-type-{race.get('registration_type', 'direct')}"
        return f"""
            <div class="race-card {urgency}">
                <div class="tier1">
                    <span class="race-name"><a href="{race.get('website', '#')}">{race['name']}</a></span>
                    <span class="days-badge {urgency}">{days} day{'s' if days != 1 else ''}</span>
                </div>
                <div class="tier2">
                    <table><tr>
                        <td><span class="date-label">Registration Opens</span><br><span class="date-value">{item['reg_date'].strftime('%B %d, %Y')}</span></td>
                        <td><span class="date-label">Race Date</span><br><span class="date-value">{format_race_date(race)}</span></td>
                        <td><span class="date-label">Type</span><br><span class="date-value"><span class="reg-type {reg_type_class}">{race.get('registration_type', 'N/A')}</span></span></td>
                    </tr></table>
                </div>
                <div class="tier3">
                    <span class="label">Location:</span> {race.get('city', '')}, {race.get('state_or_country', '')} &nbsp;
                    <span class="label">Distances:</span> {', '.join(race.get('distances', []))} &nbsp;
                    <span class="label">Elevation:</span> {format_elevation(race)}
                </div>
                {f'<div class="notes">{race.get("notes", "")}</div>' if race.get('notes') else ''}
            </div>
            """

    def render_race_card(item):
        race = item["race"]
        days = item["days_until"]
        return f"""
            <div class="race-card">
                <div class="tier1">
                    <span class="race-name"><a href="{race.get('website', '#')}">{race['name']}</a></span>
                    <span class="days-badge soon">{days} day{'s' if days != 1 else ''}</span>
                </div>
                <div class="tier2">
                    <table><tr>
                        <td><span class="date-label">Race Date</span><br><span class="date-value">{item['race_date'].strftime('%B %d, %Y')}</span></td>
                        <td><span class="date-label">Location</span><br><span class="date-value">{race.get('city', '')}, {race.get('state_or_country', '')}</span></td>
                    </tr></table>
                </div>
                <div class="tier3">
                    <span class="label">Distances:</span> {', '.join(race.get('distances', []))} &nbsp;
                    <span class="label">Elevation:</span> {format_elevation(race)} &nbsp;
                    <span class="label">Terrain:</span> {race.get('terrain', 'N/A')}
                </div>
                {f'<div class="notes">{race.get("notes", "")}</div>' if race.get('notes') else ''}
            </div>
            """

    def render_reminder_card(item):
        race = item["race"]
        return f"""
            <div class="race-card">
                <div class="tier1">
                    <span class="race-name"><a href="{race.get('website', '#')}">{race['name']}</a></span>
                    <span class="days-badge soon">{item['months_out']} out</span>
                </div>
                <div class="tier2">
                    <table><tr>
                        <td><span class="date-label">Race Date</span><br><span class="date-value">{item['race_date'].strftime('%B %d, %Y')}</span></td>
                        <td><span class="date-label">Location</span><br><span class="date-value">{race.get('city', '')}, {race.get('state_or_country', '')}</span></td>
                    </tr></table>
                </div>
                <div class="tier3">
                    <span class="label">Distances:</span> {', '.join(race.get('distances', []))}
                </div>
            </div>
            """

    if upcoming_7:
        html += '<h2>Registration Opening This Week (7 days)</h2>'
        for item in upcoming_7:
            html += render_reg_card(item, "urgent")

    only_14 = [item for item in upcoming_14 if item["days_until"] > 7]
    if only_14:
        html += '<h2>Registration Opening in 8-14 Days</h2>'
        for item in only_14:
            html += render_reg_card(item, "soon")

    if upcoming_races:
        html += '<h2>Races Coming Up (Next 14 Days)</h2>'
        for item in upcoming_races:
            html += render_race_card(item)

    if reg_reminders:
        html += """
        <h2>Registration Date Unknown - Check Soon</h2>
        <div class="warning">
            These races don't have confirmed registration dates yet. Check their websites to find out when registration opens.
        </div>
        """
        for item in reg_reminders:
            html += render_reminder_card(item)

    if not upcoming_7 and not only_14 and not upcoming_races and not reg_reminders and not seasonal_reminder:
        html += """
        <p style="color: #666; font-style: italic; margin: 30px 0;">
            No upcoming registrations or races in the next 14 days. You're all clear!
        </p>
        """

    if seasonal_reminder:
        season = "summer" if seasonal_reminder == "summer" else "new year"
        html += f"""
        <h2>Seasonal Reminder: Update Your Race List</h2>
        <div class="warning">
            <strong>It's {season} — time to update races.json!</strong><br><br>
            Check each race's website for updated registration dates and race dates for the upcoming season.
            Many races announce their next edition's details around this time of year.
        </div>
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
    reg_reminders = find_unknown_reg_reminders(races, today)
    seasonal_reminder = check_seasonal_update_reminder(today)

    has_content = upcoming_7 or upcoming_14 or upcoming_races or reg_reminders or seasonal_reminder

    if not has_content:
        print("No upcoming registrations or races. No email sent.")
        return

    html_body = build_email_html(upcoming_7, upcoming_14, upcoming_races, reg_reminders, today, seasonal_reminder)

    if upcoming_7:
        subject = f"🏃 Race Alert: {len(upcoming_7)} registration(s) opening THIS WEEK!"
    elif upcoming_14:
        only_14 = [item for item in upcoming_14 if item["days_until"] > 7]
        subject = f"🏃 Race Alert: {len(only_14)} registration(s) opening in 8-14 days"
    elif upcoming_races:
        subject = f"🏃 Race Alert: {len(upcoming_races)} race(s) coming up in the next 14 days"
    elif seasonal_reminder:
        subject = "🏃 Race Alert: Time to update your race list for the season!"
    else:
        subject = "🏃 Race Alert: Races to check - registration dates unknown"

    send_email(subject, html_body)
    print(f"Notified about {len(upcoming_14)} registration(s), {len(upcoming_races)} upcoming race(s), and {len(reg_reminders)} reminder(s).")


if __name__ == "__main__":
    main()
