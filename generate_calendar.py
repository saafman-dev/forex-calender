import requests
import hashlib
from datetime import datetime, timezone

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ISO-3 country -> currency
COUNTRIES = {
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",
}

# Eurozone countries worth checking
EURO_COUNTRIES = [
    "DEU", "FRA", "ITA", "ESP", "NLD",
    "BEL", "AUT", "IRL", "PRT", "FIN"
]

def escape_ics(value):
    value = str(value or "")
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

def parse_datetime(value):
    value = str(value).strip()

    # Handle ISO timestamps
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)

def extract_events(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["events", "data", "results", "items"]:
            value = data.get(key)
            if isinstance(value, list):
                return value

        # Some APIs return a dict of numbered objects
        values = list(data.values())
        if values and all(isinstance(x, dict) for x in values):
            return values

    return []

def fetch_country(country, currency):
    print(f"\nFetching {country} ({currency})")

    response = requests.get(
        API,
        params={
            "country": country,
            "impact": "HIGH"
        },
        timeout=90
    )

    print("URL:", response.url)
    print("Status:", response.status_code)

    response.raise_for_status()

    data = response.json()

    print("Response type:", type(data).__name__)

    if isinstance(data, dict):
        print("Top-level keys:", list(data.keys())[:20])

    rows = extract_events(data)

    print("Rows returned:", len(rows))

    output = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        impact = str(
            row.get("Impact")
            or row.get("impact")
            or ""
        ).upper()

        if impact and impact != "HIGH":
            continue

        start = (
            row.get("Start")
            or row.get("start")
            or row.get("datetime")
            or row.get("Date")
            or row.get("date")
        )

        name = (
            row.get("Name")
            or row.get("name")
            or row.get("release")
            or row.get("title")
        )

        api_currency = (
            row.get("Currency")
            or row.get("currency")
            or currency
        )

        if not start or not name:
            print("Skipping row without date/name:", row)
            continue

        try:
            dt = parse_datetime(start)
        except Exception as exc:
            print("Could not parse:", start, exc)
            continue

        uid_text = f"{api_currency}|{name}|{dt.isoformat()}"
        uid = hashlib.sha256(uid_text.encode()).hexdigest()[:24]

        output.append({
            "currency": api_currency,
            "name": name,
            "dt": dt,
            "uid": uid,
        })

    return output


events = []

# GBP, JPY, CHF, CAD, AUD, NZD
for country, currency in COUNTRIES.items():
    events.extend(fetch_country(country, currency))

# EUR
for country in EURO_COUNTRIES:
    events.extend(fetch_country(country, "EUR"))

# Remove duplicates
unique = {}

for event in events:
    key = (
        event["currency"],
        event["name"],
        event["dt"].isoformat()
    )
    unique[key] = event

events = list(unique.values())
events.sort(key=lambda event: event["dt"])

print("\nTOTAL HIGH-IMPACT EVENTS:", len(events))

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

with open(
    "global-forex-high.ics",
    "w",
    encoding="utf-8",
    newline=""
) as file:
    file.write("\r\n".join(lines) + "\r\n")

print("Calendar written successfully.")
