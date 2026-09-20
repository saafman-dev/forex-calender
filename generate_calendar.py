import requests
import hashlib
import re
from datetime import datetime, timezone, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",

    # Only the most important Euro-area national releases
    "DEU": "EUR",
    "FRA": "EUR",
    "ITA": "EUR",
    "ESP": "EUR",
}


# ============================================================
# CURRENCY-SPECIFIC IMPORTANT EVENTS
# ============================================================

PATTERNS = {

    "GBP": [
        r"\bboe\b.*\brate\b",
        r"\bbank of england\b.*\brate\b",
        r"\bofficial bank rate\b",
        r"\bmonetary policy statement\b",
        r"\bmonetary policy report\b",
        r"\bboe minutes\b",

        r"\bcpi\b",
        r"\binflation rate\b",

        r"\bunemployment rate\b",
        r"\bemployment change\b",
        r"\bclaimant count change\b",
        r"\baverage earnings\b",
        r"\baverage weekly earnings\b",

        r"\bgdp growth rate\b",

        r"\bmanufacturing pmi\b",
        r"\bservices pmi\b",
        r"\bcomposite pmi\b",

        r"\bretail sales\b",
    ],

    "JPY": [
        r"\bboj\b.*\brate\b",
        r"\bbank of japan\b.*\brate\b",
        r"\bboj monetary policy\b",
        r"\bmonetary policy statement\b",

        r"\btokyo cpi\b",
        r"\bnational cpi\b",
        r"\bcpi\b",
        r"\binflation rate\b",

        r"\bgdp growth rate\b",

        r"\bunemployment rate\b",
    ],

    "CHF": [
        r"\bsnb\b.*\brate\b",
        r"\bswiss national bank\b.*\brate\b",
        r"\bpolicy rate\b",

        r"\bcpi\b",
        r"\binflation rate\b",

        r"\bgdp growth rate\b",
        r"\bunemployment rate\b",
    ],

    "CAD": [
        r"\bboc\b.*\brate\b",
        r"\bbank of canada\b.*\brate\b",
        r"\bovernight rate\b",
        r"\bmonetary policy report\b",

        r"\bcpi\b",
        r"\binflation rate\b",

        r"\bemployment change\b",
        r"\bunemployment rate\b",

        r"\bgdp growth rate\b",

        r"\bretail sales\b",
    ],

    "AUD": [
        r"\brba\b.*\brate\b",
        r"\breserve bank of australia\b.*\brate\b",
        r"\bcash rate\b",
        r"\bmonetary policy statement\b",

        r"\bcpi\b",
        r"\binflation rate\b",

        r"\bemployment change\b",
        r"\bunemployment rate\b",

        r"\bgdp growth rate\b",

        r"\bretail sales\b",
    ],

    "NZD": [
        r"\brbnz\b.*\brate\b",
        r"\breserve bank of new zealand\b.*\brate\b",
        r"\bofficial cash rate\b",
        r"\bmonetary policy statement\b",

        r"\bcpi\b",
        r"\binflation rate\b",

        r"\bemployment change\b",
        r"\bunemployment rate\b",

        r"\bgdp growth rate\b",
    ],

    "EUR": [
        # ECB-related events if present in the national feeds
        r"\becb\b.*\brate\b",
        r"\beuropean central bank\b.*\brate\b",
        r"\bdeposit facility rate\b",
        r"\bmain refinancing rate\b",
        r"\becb press conference\b",
        r"\bmonetary policy statement\b",

        # Major national inflation
        r"\bcpi\b",
        r"\binflation rate\b",
        r"\bhicp\b",

        # Major national GDP
        r"\bgdp growth rate\b",

        # Headline PMIs
        r"\bmanufacturing pmi\b",
        r"\bservices pmi\b",
        r"\bcomposite pmi\b",

        # Major labour data
        r"\bunemployment rate\b",
    ],
}


# ============================================================
# ALWAYS EXCLUDE THESE
# ============================================================

EXCLUDE = [
    r"\bniesr\b",
    r"\bestimate\b",
    r"\bforecast\b",

    r"\bspeech\b",
    r"\bspeaks\b",
    r"\btestimony\b",

    r"\bmonthly report\b",
    r"\bbulletin\b",

    r"\bconsumer confidence\b",
    r"\bbusiness confidence\b",
    r"\beconomic sentiment\b",

    r"\bpmi prices\b",
    r"\bpmi employment\b",
    r"\bpmi new orders\b",
    r"\bpmi output\b",

    r"\bgdp deflator\b",
    r"\bgdp price index\b",

    r"\bproducer price\b",
    r"\bppi\b",

    r"\btrade balance\b",
    r"\bcurrent account\b",

    r"\bindustrial production\b",
    r"\bfactory orders\b",

    r"\bhousing\b",
    r"\bhouse price\b",
    r"\bmortgage\b",

    r"\bbond auction\b",
    r"\bbill auction\b",

    r"\bcredit card\b",
    r"\bmoney supply\b",

    r"\btourism\b",
    r"\btourist\b",

    r"\bcar registration\b",
    r"\bvehicle sales\b",
]


# ============================================================
# HELPERS
# ============================================================

def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").lower()
    ).strip()


def important_event(currency, name):

    text = normalize(name)

    # Exclusions win
    for pattern in EXCLUDE:
        if re.search(pattern, text):
            return False

    for pattern in PATTERNS.get(currency, []):
        if re.search(pattern, text):
            return True

    return False


def parse_datetime(value):

    value = str(value).strip()

    try:
        dt = datetime.strptime(
            value,
            "%m/%d/%Y %H:%M:%S"
        )

        # Temporary interpretation.
        # We will verify source timezone before publishing.
        return dt.replace(
            tzinfo=timezone.utc
        )

    except ValueError:
        pass

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


def escape_ics(value):

    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
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
# DATE RANGE
# ============================================================

now = datetime.now(
    timezone.utc
)

today = now.replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0,
)

end = today + timedelta(
    days=365
)

start_string = today.strftime(
    "%Y-%m-%d"
)

end_string = end.strftime(
    "%Y-%m-%d"
)


# ============================================================
# FETCH
# ============================================================

def fetch_country(country, currency):

    print(
        f"Fetching {country} ({currency})..."
    )

    response = requests.get(
        API,
        params={
            "country": country,
            "impact": "HIGH",
            "type": "Release",
            "start_date": start_string,
            "end_date": end_string,
        },
        timeout=90,
    )

    print(
        "Status:",
        response.status_code
    )

    response.raise_for_status()

    rows = extract_events(
        response.json()
    )

    print(
        "API rows:",
        len(rows)
    )

    accepted = []

    for row in rows:

        if not isinstance(row, dict):
            continue

        name = (
            row.get("Name")
            or row.get("name")
            or row.get("release")
            or row.get("title")
        )

        start = (
            row.get("Start")
            or row.get("start")
            or row.get("datetime")
            or row.get("date")
        )

        if not name or not start:
            continue

        if not important_event(
            currency,
            name
        ):
            continue

        try:
            dt = parse_datetime(start)

        except Exception as error:

            print(
                "Bad date:",
                start,
                error
            )

            continue

        accepted.append({
            "currency": currency,
            "country": country,
            "name": str(name),
            "dt": dt,
        })

    print(
        "Accepted:",
        len(accepted)
    )

    return accepted


events = []


for country, currency in COUNTRIES.items():

    events.extend(
        fetch_country(
            country,
            currency
        )
    )


# ============================================================
# REMOVE DUPLICATES
# ============================================================

unique = {}


for event in events:

    key = (
        event["currency"],
        normalize(event["name"]),
        event["dt"].isoformat(),
    )

    unique[key] = event


events = list(
    unique.values()
)

events.sort(
    key=lambda event: event["dt"]
)


print("")
print("==========================")
print("FINAL EVENTS:", len(events))
print("==========================")
print("")


# ============================================================
# PRINT BREAKDOWN
# ============================================================

for currency in [
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
]:

    count = sum(
        1
        for event in events
        if event["currency"] == currency
    )

    print(
        f"{currency}: {count}"
    )


# ============================================================
# CREATE ICS
# ============================================================

dtstamp = now.strftime(
    "%Y%m%dT%H%M%SZ"
)


lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//saafman-dev//Global Forex High Impact//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:🌍 Global Forex — High Impact",
    "X-WR-CALDESC:Major forex market events excluding USD",
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


print("")
print(
    "Calendar created with",
    len(events),
    "events."
)
