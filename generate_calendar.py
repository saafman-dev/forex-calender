import requests
import hashlib
import re
from datetime import datetime, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# COUNTRIES
# ============================================================

# USD deliberately excluded because AIO already covers it.
#
# For EUR we use Germany as the national macro feed.
# This avoids duplicating French/Italian/Spanish releases.
COUNTRIES = {
    "DEU": "EUR",
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",
}


# ============================================================
# IMPORTANT EVENTS PER CURRENCY
# ============================================================

PATTERNS = {

    # --------------------------------------------------------
    # EUR
    # --------------------------------------------------------

    "EUR": [
        # Inflation
        r"\binflation rate\b",
        r"\bcpi\b",
        r"\bhicp\b",

        # GDP
        r"\bgdp growth rate\b",

        # Germany PMIs
        r"\bmanufacturing pmi\b",
        r"\bservices pmi\b",

        # Labour
        r"\bunemployment rate\b",
        r"\bunemployment change\b",

        # ECB if the feed happens to expose it
        r"\becb\b.*\brate\b",
        r"\beuropean central bank\b.*\brate\b",
        r"\bdeposit facility rate\b",
        r"\bmain refinancing rate\b",
        r"\becb press conference\b",
    ],


    # --------------------------------------------------------
    # GBP
    # --------------------------------------------------------

    "GBP": [
        # Bank of England
        r"\bofficial bank rate\b",
        r"\bboe\b.*\brate\b",
        r"\bbank of england\b.*\brate\b",
        r"\bboe minutes\b",
        r"\bmonetary policy report\b",

        # Inflation
        r"\binflation rate\b",
        r"\bcpi\b",

        # Jobs / wages
        r"\bunemployment rate\b",
        r"\bclaimant count change\b",
        r"\bemployment change\b",
        r"\baverage earnings\b",
        r"\baverage weekly earnings\b",

        # GDP
        r"\bgdp growth rate\b",

        # PMI
        r"\bmanufacturing pmi\b",
        r"\bservices pmi\b",

        # Consumption
        r"\bretail sales\b",
    ],


    # --------------------------------------------------------
    # JPY
    # --------------------------------------------------------

    "JPY": [
        # BoJ
        r"\bboj\b.*\brate\b",
        r"\bbank of japan\b.*\brate\b",
        r"\bboj monetary policy\b",

        # Inflation
        r"\btokyo cpi\b",
        r"\bnational cpi\b",
        r"\binflation rate\b",
        r"\bcpi\b",

        # GDP
        r"\bgdp growth rate\b",

        # Jobs
        r"\bunemployment rate\b",
    ],


    # --------------------------------------------------------
    # CHF
    # --------------------------------------------------------

    "CHF": [
        # SNB
        r"\bsnb\b.*\brate\b",
        r"\bswiss national bank\b.*\brate\b",
        r"\bpolicy rate\b",

        # Inflation
        r"\binflation rate\b",
        r"\bcpi\b",

        # GDP
        r"\bgdp growth rate\b",

        # Jobs
        r"\bunemployment rate\b",
    ],


    # --------------------------------------------------------
    # CAD
    # --------------------------------------------------------

    "CAD": [
        # Bank of Canada
        r"\bboc\b.*\brate\b",
        r"\bbank of canada\b.*\brate\b",
        r"\bovernight rate\b",
        r"\bmonetary policy report\b",

        # Inflation
        r"\binflation rate\b",
        r"\bcpi\b",

        # Jobs
        r"\bemployment change\b",
        r"\bunemployment rate\b",

        # GDP
        r"\bgdp growth rate\b",

        # Consumption
        r"\bretail sales\b",
    ],


    # --------------------------------------------------------
    # AUD
    # --------------------------------------------------------

    "AUD": [
        # RBA
        r"\brba\b.*\brate\b",
        r"\breserve bank of australia\b.*\brate\b",
        r"\bcash rate\b",
        r"\bmonetary policy statement\b",

        # Inflation
        r"\binflation rate\b",
        r"\bcpi\b",

        # Jobs
        r"\bemployment change\b",
        r"\bunemployment rate\b",

        # GDP
        r"\bgdp growth rate\b",

        # Consumption
        r"\bretail sales\b",
    ],


    # --------------------------------------------------------
    # NZD
    # --------------------------------------------------------

    "NZD": [
        # RBNZ
        r"\brbnz\b.*\brate\b",
        r"\breserve bank of new zealand\b.*\brate\b",
        r"\bofficial cash rate\b",
        r"\bmonetary policy statement\b",

        # Inflation
        r"\binflation rate\b",
        r"\bcpi\b",

        # Jobs
        r"\bemployment change\b",
        r"\bunemployment rate\b",

        # GDP
        r"\bgdp growth rate\b",
    ],
}


# ============================================================
# ALWAYS EXCLUDE
# ============================================================

EXCLUDE = [

    # Forecasts / estimates
    r"\bniesr\b",
    r"\bestimate\b",
    r"\bforecast\b",

    # Speeches
    r"\bspeech\b",
    r"\bspeaks\b",
    r"\btestimony\b",
    r"\bappearance\b",

    # Secondary reports
    r"\bmonthly report\b",
    r"\bbulletin\b",

    # Confidence
    r"\bconsumer confidence\b",
    r"\bbusiness confidence\b",
    r"\beconomic sentiment\b",

    # PMI sub-indices / duplicate composite
    r"\bcomposite pmi\b",
    r"\bpmi prices\b",
    r"\bpmi employment\b",
    r"\bpmi new orders\b",
    r"\bpmi output\b",

    # GDP secondary data
    r"\bgdp deflator\b",
    r"\bgdp price index\b",

    # Producer prices
    r"\bproducer price\b",
    r"\bppi\b",
    r"\bwholesale price\b",

    # Trade
    r"\btrade balance\b",
    r"\bcurrent account\b",
    r"\bexports\b",
    r"\bimports\b",

    # Production
    r"\bindustrial production\b",
    r"\bmanufacturing production\b",
    r"\bfactory orders\b",

    # Housing
    r"\bhousing starts\b",
    r"\bhouse price\b",
    r"\bbuilding permits\b",
    r"\bmortgage\b",
    r"\bhome loans\b",

    # Credit / money
    r"\bcredit card\b",
    r"\bmoney supply\b",

    # Auctions
    r"\bbond auction\b",
    r"\bbill auction\b",

    # Other
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


def is_important(currency, name):

    text = normalize(name)

    for pattern in EXCLUDE:
        if re.search(pattern, text):
            return False

    for pattern in PATTERNS.get(currency, []):
        if re.search(pattern, text):
            return True

    return False


def parse_datetime(value):

    value = str(value).strip()

    # API format:
    # MM/DD/YYYY HH:MM:SS
    try:
        return datetime.strptime(
            value,
            "%m/%d/%Y %H:%M:%S"
        )

    except ValueError:
        pass

    # ISO fallback
    value = value.replace(
        "Z",
        "+00:00"
    )

    dt = datetime.fromisoformat(value)

    # Strip timezone temporarily.
    # We will only assign UTC after verifying
    # what timezone the source actually uses.
    return dt.replace(
        tzinfo=None
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

now = datetime.utcnow()

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

    print("")
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

        if not is_important(
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
            "country": country,
            "currency": currency,
            "name": str(name),
            "dt": dt,

            # Use source ID when available.
            "source_id": (
                row.get("Id")
                or row.get("id")
            ),
        })

    print(
        "Accepted:",
        len(accepted)
    )

    return accepted


# ============================================================
# COLLECT
# ============================================================

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
        event["country"],
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


# ============================================================
# RESULTS
# ============================================================

print("")
print("==============================")
print("FINAL EVENTS:", len(events))
print("==============================")

for currency in [
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
]:

    currency_events = [
        event
        for event in events
        if event["currency"] == currency
    ]

    print("")
    print(
        f"{currency}: {len(currency_events)}"
    )

    # Show unique event names so we can inspect
    # exactly what the calendar contains.
    names = sorted(
        {
            event["name"]
            for event in currency_events
        }
    )

    for name in names:
        print(
            f"  - {name}"
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

    # IMPORTANT:
    # No Z for now.
    #
    # We first need to establish what timezone the
    # API's timezone-less Start field represents.
    start = event["dt"].strftime(
        "%Y%m%dT%H%M%S"
    )

    # Prefer stable source ID.
    if event["source_id"]:

        uid_base = str(
            event["source_id"]
        )

    else:

        uid_base = (
            f"{event['country']}|"
            f"{event['currency']}|"
            f"{event['name']}|"
            f"{event['dt'].isoformat()}"
        )

    uid_hash = hashlib.sha256(
        uid_base.encode("utf-8")
    ).hexdigest()[:24]

    # NOTE:
    # Do NOT escape the @ sign.
    uid = (
        f"{uid_hash}"
        f"@saafman-dev.github.io"
    )

    lines.extend([

        "BEGIN:VEVENT",

        f"UID:{uid}",

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
print("==============================")
print(
    "Calendar created with",
    len(events),
    "events."
)
print("==============================")
