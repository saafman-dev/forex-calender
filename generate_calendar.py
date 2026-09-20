import requests
import hashlib
import re
from datetime import datetime, timezone, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# CURRENCIES
# USD intentionally excluded — AIO handles USD.
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


# ============================================================
# STRICT HIGH-IMPACT FILTER
# ============================================================

# These are the event families we actually want.
IMPORTANT_PATTERNS = [

    # --------------------------------------------------------
    # CENTRAL BANKS / RATES
    # --------------------------------------------------------

    r"\binterest rate decision\b",
    r"\binterest rate\b",
    r"\brate decision\b",
    r"\bpolicy rate\b",
    r"\bofficial bank rate\b",
    r"\bcash rate\b",

    r"\bmonetary policy statement\b",
    r"\bmonetary policy report\b",
    r"\bmonetary policy decision\b",

    r"\becb press conference\b",
    r"\becb interest rate\b",
    r"\becb rate\b",

    r"\bboe interest rate\b",
    r"\bboe rate\b",
    r"\bboe minutes\b",

    r"\bboj interest rate\b",
    r"\bboj rate\b",
    r"\bboj monetary policy\b",

    r"\bsnb interest rate\b",
    r"\bsnb rate\b",
    r"\bsnb monetary policy\b",

    r"\bboc interest rate\b",
    r"\bboc rate\b",
    r"\bbank of canada interest rate\b",

    r"\brba interest rate\b",
    r"\brba rate\b",
    r"\brba monetary policy\b",

    r"\brbnz interest rate\b",
    r"\brbnz rate\b",
    r"\brbnz monetary policy\b",

    # --------------------------------------------------------
    # CPI / INFLATION
    # --------------------------------------------------------

    r"\bcpi\b",
    r"\bconsumer price index\b",
    r"\binflation rate\b",
    r"\bcore inflation rate\b",
    r"\bhicp\b",

    # --------------------------------------------------------
    # LABOUR MARKET
    # --------------------------------------------------------

    r"\bunemployment rate\b",
    r"\bemployment change\b",
    r"\bunemployment change\b",

    # UK claimant count is an important GBP release
    r"\bclaimant count change\b",

    # Canada/Australia/NZ labour reports
    r"\bemployment change\b",
    r"\bfull time employment change\b",
    r"\bparticipation rate\b",

    # --------------------------------------------------------
    # GDP — official growth releases only
    # --------------------------------------------------------

    r"\bgdp growth rate\b",
    r"\bgdp growth\b",
    r"\bgross domestic product\b",

    # --------------------------------------------------------
    # PMI — major headline PMIs only
    # --------------------------------------------------------

    r"\bmanufacturing pmi\b",
    r"\bservices pmi\b",
    r"\bcomposite pmi\b",

    # --------------------------------------------------------
    # RETAIL SALES
    # --------------------------------------------------------

    r"\bretail sales\b",

    # --------------------------------------------------------
    # WAGES — selected major wage releases
    # --------------------------------------------------------

    r"\baverage earnings\b",
    r"\baverage weekly earnings\b",
    r"\bwage price index\b",
]


# These override the patterns above.
# If one of these is found, the event is always rejected.
EXCLUDE_PATTERNS = [

    # Forecasts / estimates
    r"\bniesr\b",
    r"\bestimate\b",
    r"\bforecast\b",

    # Speeches / appearances
    r"\bspeech\b",
    r"\bspeaks\b",
    r"\btestimony\b",
    r"\bappearance\b",

    # Secondary central-bank material
    r"\bmonthly report\b",
    r"\bbulletin\b",

    # PMI sub-indices
    r"\bpmi prices\b",
    r"\bpmi employment\b",
    r"\bpmi new orders\b",
    r"\bpmi output\b",

    # GDP secondary details
    r"\bgdp deflator\b",
    r"\bgdp price index\b",

    # Labour secondary indicators
    r"\bemployment expectations\b",

    # Surveys / confidence
    r"\bconsumer confidence\b",
    r"\bbusiness confidence\b",
    r"\beconomic sentiment\b",

    # Housing
    r"\bhouse price\b",
    r"\bhousing starts\b",
    r"\bbuilding permits\b",
    r"\bmortgage\b",
    r"\bhome loans\b",

    # Trade
    r"\btrade balance\b",
    r"\bcurrent account\b",
    r"\bexports\b",
    r"\bimports\b",

    # Industrial / factory
    r"\bindustrial production\b",
    r"\bmanufacturing production\b",
    r"\bfactory orders\b",

    # Prices other than CPI
    r"\bproducer price\b",
    r"\bppi\b",
    r"\bwholesale price\b",

    # Money / credit
    r"\bmoney supply\b",
    r"\bcredit card\b",
    r"\bprivate sector credit\b",

    # Auctions / government
    r"\bbond auction\b",
    r"\bbill auction\b",
    r"\bgovernment debt\b",
    r"\bgovernment budget\b",

    # Other low-priority releases
    r"\bcar registration\b",
    r"\bvehicle sales\b",
    r"\btourist\b",
    r"\btourism\b",
]


def normalize(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or "").lower()
    ).strip()


def is_important(name):

    text = normalize(name)

    # Exclusion always wins.
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, text):
            return False

    for pattern in IMPORTANT_PATTERNS:
        if re.search(pattern, text):
            return True

    return False


# ============================================================
# DATE HANDLING
# ============================================================

def parse_datetime(value):

    value = str(value).strip()

    # Current source format:
    # MM/DD/YYYY HH:MM:SS
    try:
        return datetime.strptime(
            value,
            "%m/%d/%Y %H:%M:%S"
        ).replace(
            tzinfo=timezone.utc
        )

    except ValueError:
        pass

    # ISO fallback
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


# ============================================================
# ICS
# ============================================================

def escape_ics(value):

    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


# ============================================================
# API
# ============================================================

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

            if isinstance(
                data.get(key),
                list
            ):
                return data[key]

    return []


def fetch_country(
    country,
    currency,
    start_date,
    end_date,
):

    print(
        f"Fetching {country} ({currency})..."
    )

    response = requests.get(
        API,
        params={
            "country": country,
            "impact": "HIGH",
            "type": "Release",
            "start_date": start_date,
            "end_date": end_date,
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

        if not is_important(name):
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
            "name": str(name),
            "dt": dt,
        })

    print(
        "Accepted:",
        len(accepted)
    )

    return accepted


# ============================================================
# DATE WINDOW
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

# 12 months forward
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

events = []


for country, currency in COUNTRIES.items():

    events.extend(
        fetch_country(
            country,
            currency,
            start_string,
            end_string,
        )
    )


for country in EURO_COUNTRIES:

    events.extend(
        fetch_country(
            country,
            "EUR",
            start_string,
            end_string,
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
    key=lambda x: x["dt"]
)


print("")
print("============================")
print("FINAL EVENTS:", len(events))
print("============================")
print("")


# ============================================================
# BUILD ICS
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
        uid_source.encode()
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


print(
    "Calendar created with",
    len(events),
    "events."
)
