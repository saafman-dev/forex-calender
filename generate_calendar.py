import requests
import hashlib
from datetime import datetime, timezone

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# Countries/currencies we want.
# USD is intentionally excluded because AIO already covers US events.
COUNTRIES = {
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",
}

EURO_COUNTRIES = [
    "DEU",
    "FRA",
    "ITA",
    "ESP",
    "NLD",
    "BEL",
    "AUT",
    "IRL",
    "PRT",
    "FIN",
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

    # Main format returned by this API:
    # MM/DD/YYYY HH:MM:SS
    try:
        dt = datetime.strptime(value, "%m/%d/%Y %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Fallback for ISO timestamps
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except ValueError:
        raise ValueError(f"Unknown date format: {value}")


def extract_events(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["events", "data", "results", "items"]:
            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


def fetch_country(country, default_currency):
    print(f"Fetching {country} ({default_currency})...")

    response = requests.get(
        API,
        params={
            "country": country,
            "impact": "HIGH",
        },
        timeout=90,
    )

    print("Status:", response.status_code)
    response.raise_for_status()

    data = response.json()
    rows = extract_events(data)

    print("Rows returned:", len(rows))

    output = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        # Extra safety check: only HIGH impact.
        impact = str(
            row.get("Impact")
            or row.get("impact")
            or ""
        ).strip().upper()

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

        currency = (
            row.get("Currency")
            or row.get("currency")
            or default_currency
        )

        currency = str(currency).upper().strip()

        # Never include USD.
        if currency == "USD":
            continue

        if not start or not name:
            continue

        try:
            dt = parse_datetime(start)
        except Exception as error:
            print("Skipping date:", start, error)
            continue

        uid_source = f"{currency}|{name}|{dt.isoformat()}"

        uid = hashlib.sha256(
            uid_source.encode("utf-8")
        ).hexdigest()[:24]

        output.append({
            "currency": currency,
            "name": str(name),
            "dt": dt,
            "uid": uid,
        })

    return output


events = []

# GBP, JPY, CHF, CAD, AUD and NZD
for country, currency in COUNTRIES.items():
    events.extend(
        fetch_country(country, currency)
    )

# EUR events
for country in EURO_COUNTRIES:
    country_events = fetch_country(country, "EUR")

    for event in country_events:
        # Force euro-area events to EUR
        event["currency"] = "EUR"

    events.extend(country_events)


# Remove duplicates
unique_events = {}

for event in events:
    key = (
        event["currency"],
        event["name"],
        event["dt"].isoformat(),
    )

    unique_events[key] = event


events = list(unique_events.values())

events.sort(
    key=lambda event: event["dt"]
)


print("")
print(
    "TOTAL HIGH-IMPACT EVENTS:",
    len(events)
)


# Create the ICS calendar
now = datetime.now(
    timezone.utc
).strftime("%Y%m%dT%H%M%SZ")


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

    start = event["dt"].strftime(
        "%Y%m%dT%H%M%SZ"
    )

    lines.extend([
        "BEGIN:VEVENT",

        f"UID:{event['uid']}@saafman-dev.github.io",

        f"DTSTAMP:{now}",

        f"DTSTART:{start}",

        f"SUMMARY:🔴 {event['currency']} — "
        f"{escape_ics(event['name'])}",

        f"DESCRIPTION:High-impact "
        f"{event['currency']} economic event.",

        "BEGIN:VALARM",

        "TRIGGER:-PT30M",

        "ACTION:DISPLAY",

        "DESCRIPTION:High-impact market event in 30 minutes",

        "END:VALARM",

        "END:VEVENT",
    ])


lines.append(
    "END:VCALENDAR"
)


with open(
    "global-forex-high.ics",
    "w",
    encoding="utf-8",
    newline="",
) as file:

    file.write(
        "\r\n".join(lines) + "\r\n"
    )


print(
    f"Calendar created with "
    f"{len(events)} events."
)
