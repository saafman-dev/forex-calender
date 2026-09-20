import requests
import hashlib
import re
from datetime import datetime, timezone, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# SETTINGS
# ============================================================

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

ALLOWED_CURRENCIES = {
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
}

# Keep only events that contain one of these terms.
IMPORTANT_TERMS = [
    # Central banks / interest rates
    "interest rate",
    "rate decision",
    "rate statement",
    "monetary policy",
    "monetary policy statement",
    "monetary policy report",
    "central bank",
    "press conference",
    "policy rate",
    "cash rate",
    "official bank rate",
    "bank rate",
    "deposit facility rate",
    "refinancing rate",
    "overnight rate",

    # Inflation
    "consumer price index",
    "cpi",
    "inflation rate",
    "core inflation",
    "harmonised index of consumer prices",
    "harmonized index of consumer prices",
    "hicp",

    # Employment
    "employment change",
    "unemployment rate",
    "unemployment change",
    "unemployment",
    "employment rate",
    "jobless rate",
    "claimant count",
    "labor force",
    "labour force",

    # GDP
    "gross domestic product",
    "gdp",

    # Major activity indicators
    "manufacturing pmi",
    "services pmi",
    "composite pmi",

    # Consumption
    "retail sales",

    # Wages
    "average earnings",
    "average weekly earnings",
    "wage price index",
    "wage growth",

    # Important central-bank specific events
    "ecb",
    "bank of england",
    "boe",
    "bank of japan",
    "boj",
    "snb",
    "swiss national bank",
    "bank of canada",
    "boc",
    "reserve bank of australia",
    "rba",
    "reserve bank of new zealand",
    "rbnz",
]


# Things that are often labelled important by datasets but
# aren't useful enough for this clean trading calendar.
EXCLUDE_TERMS = [
    "credit card spending",
    "buba monthly report",
    "bundesbank monthly report",
    "consumer confidence",
    "business confidence",
    "economic sentiment",
    "construction output",
    "industrial production",
    "factory orders",
    "trade balance",
    "current account",
    "government budget",
    "government debt",
    "bond auction",
    "car registrations",
    "vehicle sales",
    "housing starts",
    "building permits",
    "house price",
    "home loans",
    "mortgage",
    "tourist arrivals",
    "tourism",
    "foreign exchange reserves",
    "money supply",
    "producer price",
    "ppi",
    "wholesale prices",
]


# ============================================================
# ICS HELPERS
# ============================================================

def escape_ics(value):
    value = str(value or "")

    return (
        value
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def parse_datetime(value):
    value = str(value).strip()

    # API format:
    # MM/DD/YYYY HH:MM:SS
    try:
        dt = datetime.strptime(
            value,
            "%m/%d/%Y %H:%M:%S"
        )

        return dt.replace(
            tzinfo=timezone.utc
        )

    except ValueError:
        pass

    # ISO fallback
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except ValueError:
        raise ValueError(
            f"Unknown date format: {value}"
        )


def extract_events(data):

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in [
            "events",
            "data",
            "results",
            "items",
        ]:

            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


# ============================================================
# EVENT FILTER
# ============================================================

def normalize(text):
    text = str(text or "").lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def is_important_event(name):

    name = normalize(name)

    # First remove unwanted events
    for term in EXCLUDE_TERMS:

        if term in name:
            return False

    # Then check important events
    for term in IMPORTANT_TERMS:

        if term in name:
            return True

    return False


# ============================================================
# FETCH EVENTS
# ============================================================

def fetch_country(
    country,
    default_currency
):

    print(
        f"Fetching {country} "
        f"({default_currency})..."
    )

    response = requests.get(
        API,
        params={
            "country": country,
            "impact": "HIGH",
        },
        timeout=90,
    )

    print(
        "Status:",
        response.status_code
    )

    response.raise_for_status()

    data = response.json()

    rows = extract_events(data)

    print(
        "Rows returned:",
        len(rows)
    )

    output = []

    for row in rows:

        if not isinstance(row, dict):
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

        if not start or not name:
            continue

        currency = str(
            currency
        ).upper().strip()

        # Never include USD
        if currency == "USD":
            continue

        # Force euro-area countries to EUR
        if default_currency == "EUR":
            currency = "EUR"

        if currency not in ALLOWED_CURRENCIES:
            continue

        # Only our important events
        if not is_important_event(name):
            continue

        try:

            dt = parse_datetime(start)

        except Exception as error:

            print(
                "Skipping bad date:",
                start,
                error
            )

            continue

        output.append({
            "currency": currency,
            "name": str(name),
            "dt": dt,
        })

    return output


# ============================================================
# COLLECT
# ============================================================

events = []


# GBP / JPY / CHF / CAD / AUD / NZD
for country, currency in COUNTRIES.items():

    events.extend(
        fetch_country(
            country,
            currency
        )
    )


# EUR
for country in EURO_COUNTRIES:

    events.extend(
        fetch_country(
            country,
            "EUR"
        )
    )


# ============================================================
# DATE RANGE
# ============================================================

now_dt = datetime.now(
    timezone.utc
)

today = now_dt.replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0,
)

end_date = (
    today
    + timedelta(days=365)
)


events = [
    event
    for event in events

    if today
    <= event["dt"]
    <= end_date
]


# ============================================================
# REMOVE DUPLICATES
# ============================================================

unique_events = {}


for event in events:

    # Remove country duplicates for EUR releases
    key = (
        event["currency"],
        normalize(event["name"]),
        event["dt"].isoformat(),
    )

    unique_events[key] = event


events = list(
    unique_events.values()
)


events.sort(
    key=lambda event: event["dt"]
)


print("")
print(
    "FINAL EVENTS:",
    len(events)
)


# ============================================================
# BUILD CALENDAR
# ============================================================

dtstamp = now_dt.strftime(
    "%Y%m%dT%H%M%SZ"
)


lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//saafman-dev//Global Forex High Impact//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:🌍 Global Forex — High Impact",
    "X-WR-CALDESC:Major global forex events excluding USD",
]


for event in events:

    start = event["dt"].strftime(
        "%Y%m%dT%H%M%SZ"
    )

    uid_source = (
        f"{event['currency']}|"
        f"{event['name']}|"
        f"{event['dt'].isoformat()}"
    )

    uid = hashlib.sha256(
        uid_source.encode("utf-8")
    ).hexdigest()[:24]

    lines.extend([
        "BEGIN:VEVENT",

        f"UID:{uid}@saafman-dev.github.io",

        f"DTSTAMP:{dtstamp}",

        f"DTSTART:{start}",

        (
            f"SUMMARY:🔴 "
            f"{event['currency']} — "
            f"{escape_ics(event['name'])}"
        ),

        (
            f"DESCRIPTION:"
            f"Major {event['currency']} "
            f"economic event."
        ),

        "BEGIN:VALARM",

        "TRIGGER:-PT30M",

        "ACTION:DISPLAY",

        (
            "DESCRIPTION:"
            "Major market event "
            "in 30 minutes"
        ),

        "END:VALARM",

        "END:VEVENT",
    ])


lines.append(
    "END:VCALENDAR"
)


# ============================================================
# SAVE
# ============================================================

with open(
    "global-forex-high.ics",
    "w",
    encoding="utf-8",
    newline="",
) as file:

    file.write(
        "\r\n".join(lines)
        + "\r\n"
    )


print(
    f"Calendar created with "
    f"{len(events)} events."
)
