import requests
import hashlib
from datetime import datetime, timezone

API = "https://economic-calendar-api-h9hr.onrender.com/events"

COUNTRIES = {
    "EUR": "EUR",
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",
}

def escape_ics(text):
    text = str(text or "")
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

def parse_date(value):
    value = str(value).strip()

    # API normally supplies ISO-style timestamps
    value = value.replace("Z", "+00:00")

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)

events = []

for country, currency in COUNTRIES.items():
    print(f"Fetching {currency}...")

    response = requests.get(
        API,
        params={
            "country": country,
            "impact": "HIGH"
        },
        timeout=60
    )

    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        data = data.get("events", data.get("data", data.get("results", [])))

    for event in data:
        start = (
            event.get("Start")
            or event.get("start")
            or event.get("datetime")
            or event.get("date")
        )

        name = (
            event.get("Name")
            or event.get("name")
            or event.get("release")
            or event.get("title")
        )

        if not start or not name:
            continue

        try:
            dt = parse_date(start)
        except Exception:
            print("Skipping unrecognised date:", start)
            continue

        uid_source = f"{currency}|{name}|{dt.isoformat()}"
        uid = hashlib.sha256(uid_source.encode()).hexdigest()[:24]

        events.append({
            "currency": currency,
            "name": name,
            "dt": dt,
            "uid": uid
        })

events.sort(key=lambda x: x["dt"])

now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//saafman-dev//Global Forex High Impact//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:🌍 Global Forex — High Impact",
    "X-WR-CALDESC:High-impact global forex events excluding USD",
]

for event in events:
    start = event["dt"].strftime("%Y%m%dT%H%M%SZ")

    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{event['uid']}@saafman-dev.github.io",
        f"DTSTAMP:{now}",
        f"DTSTART:{start}",
        f"DTEND:{start}",
        f"SUMMARY:🔴 {event['currency']} — {escape_ics(event['name'])}",
        f"DESCRIPTION:High-impact {event['currency']} economic event.",
        "BEGIN:VALARM",
        "TRIGGER:-PT30M",
        "ACTION:DISPLAY",
        "DESCRIPTION:High-impact market event in 30 minutes",
        "END:VALARM",
        "END:VEVENT",
    ])

lines.append("END:VCALENDAR")

with open("global-forex-high.ics", "w", encoding="utf-8", newline="\r\n") as f:
    f.write("\r\n".join(lines) + "\r\n")

print(f"Created calendar with {len(events)} high-impact events.")
