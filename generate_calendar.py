import requests
import hashlib
import re
from datetime import datetime, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# COUNTRIES
# USD excluded because AIO already covers USD.
# ============================================================

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
# HELPERS
# ============================================================

def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").lower()
    ).strip()


def contains(text, patterns):
    text = normalize(text)

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# ============================================================
# FILTERS
# ============================================================

def important_eur(name):

    text = normalize(name)

    # Remove German state/regional releases
    REGIONS = [
        "baden-wurttemberg",
        "baden-württemberg",
        "bavaria",
        "brandenburg",
        "hesse",
        "north rhine-westphalia",
        "saxony",
    ]

    if any(region in text for region in REGIONS):
        return False

    # No Composite PMI — Manufacturing + Services are enough
    if "composite pmi" in text:
        return False

    return contains(text, [
        r"\bgerman cpi\b",
        r"^cpi \(mom\)$",
        r"^cpi \(yoy\)$",
        r"\binflation rate\b",

        r"\bhcob manufacturing pmi\b",
        r"\bhcob services pmi\b",

        r"\bunemployment change\b",
        r"\bunemployment rate\b",

        r"\bgdp growth rate\b",

        # ECB, if present in German feed
        r"\becb.*interest rate\b",
        r"\becb.*rate decision\b",
        r"\bdeposit facility rate\b",
        r"\bmain refinancing rate\b",
        r"\becb press conference\b",
    ])


def important_gbp(name):

    text = normalize(name)

    # Secondary/duplicate UK releases
    if contains(text, [
        r"\bbrc\b",
        r"\bilo unemployment\b",
        r"\bretail sales ex-fuel\b",
        r"\bniesr\b",
        r"\bcomposite pmi\b",
    ]):
        return False

    return contains(text, [

        # BoE
        r"\bofficial bank rate\b",
        r"\bboe interest rate\b",
        r"\bboe rate decision\b",
        r"\bboe minutes\b",
        r"\bmonetary policy report\b",

        # Inflation
        r"\bcpi \(mom\)\b",
        r"\bcpi \(yoy\)\b",
        r"\binflation rate\b",

        # Labour
        r"\bclaimant count change\b",
        r"\bemployment change\b",
        r"\bunemployment rate\b",

        # Keep one headline earnings measure
        r"\baverage earnings including bonus\b",

        # GDP
        r"\bgdp growth rate\b",

        # PMI
        r"\bs&p global manufacturing pmi\b",
        r"\bs&p global services pmi\b",

        # Retail
        r"^retail sales \(mom\)$",
    ])


def important_jpy(name):

    text = normalize(name)

    # Keep core CPI variants, not every CPI variant
    return contains(text, [

        # BoJ
        r"\bboj interest rate decision\b",
        r"\bbank of japan interest rate\b",
        r"\bboj monetary policy\b",

        # CPI
        r"\bnational cpi ex food, energy\b",
        r"\bnational cpi ex fresh food\b",
        r"\btokyo cpi ex fresh food\b",

        # GDP
        r"\bgdp growth rate\b",

        # Labour
        r"^unemployment rate$",
    ])


def important_chf(name):

    return contains(name, [

        # SNB
        r"\bsnb interest rate decision\b",
        r"\bsnb policy rate\b",
        r"\bswiss national bank.*rate\b",

        # CPI
        r"\bcpi \(mom\)\b",
        r"\bcpi \(yoy\)\b",
        r"\binflation rate\b",

        # GDP
        r"\bgdp growth rate\b",

        # Labour
        r"\bunemployment rate\b",
    ])


def important_cad(name):

    text = normalize(name)

    # Remove secondary retail variant
    if "retail sales ex autos" in text:
        return False

    return contains(text, [

        # BoC
        r"\bboc interest rate decision\b",
        r"\bboc rate decision\b",
        r"\bbank of canada.*interest rate\b",
        r"\bovernight rate\b",
        r"\bboc monetary policy report\b",

        # Inflation
        r"\bcpi \(mom\)\b",
        r"\bcpi \(yoy\)\b",
        r"\btrimmed mean cpi\b",
        r"\bmedian cpi\b",

        # Labour
        r"\bemployment change\b",
        r"^unemployment rate$",

        # GDP
        r"\bgdp growth rate\b",

        # Retail
        r"^retail sales \(mom\)$",
    ])


def important_aud(name):

    text = normalize(name)

    # We want quarterly trimmed mean, not monthly duplicates
    if (
        "trimmed mean cpi" in text
        and "quarterly" not in text
    ):
        return False

    return contains(text, [

        # RBA
        r"\brba interest rate decision\b",
        r"\brba rate decision\b",
        r"\brba cash rate\b",
        r"\bcash rate target\b",
        r"\breserve bank of australia.*rate\b",
        r"\bmonetary policy decision\b",

        # Inflation
        r"\bquarterly.*trimmed mean cpi\b",
        r"\bcpi \(qoq\)\b",
        r"\bcpi \(yoy\)\b",

        # Labour
        r"\bemployment change\b",
        r"\bunemployment rate\b",

        # GDP
        r"\bgdp growth rate\b",

        # Retail
        r"^retail sales \(mom\)$",
    ])


def important_nzd(name):

    return contains(name, [

        # RBNZ / OCR
        r"\brbnz interest rate decision\b",
        r"\brbnz rate decision\b",
        r"\bofficial cash rate\b",
        r"\bocr\b",
        r"\bmonetary policy statement\b",

        # Inflation
        r"\bcpi \(qoq\)\b",
        r"\bcpi \(yoy\)\b",
        r"\binflation rate\b",

        # Labour
        r"\bemployment change\b",
        r"^unemployment rate$",

        # GDP
        r"\bgdp growth rate\b",
    ])


FILTERS = {
    "EUR": important_eur,
    "GBP": important_gbp,
    "JPY": important_jpy,
    "CHF": important_chf,
    "CAD": important_cad,
    "AUD": important_aud,
    "NZD": important_nzd,
}


# ============================================================
# GLOBAL EXCLUSIONS
# ============================================================

GLOBAL_EXCLUDE = [
    r"\bspeech\b",
    r"\bspeaks\b",
    r"\btestimony\b",
    r"\bappearance\b",

    r"\bconsumer confidence\b",
    r"\bbusiness confidence\b",

    r"\bproducer price\b",
    r"\bppi\b",

    r"\btrade balance\b",
    r"\bcurrent account\b",

    r"\bindustrial production\b",
    r"\bfactory orders\b",

    r"\bhousing\b",
    r"\bmortgage\b",

    r"\bbond auction\b",
    r"\bbill auction\b",

    r"\bcredit card\b",
    r"\bmoney supply\b",

    r"\btourism\b",
]


def is_important(currency, name):

    if contains(name, GLOBAL_EXCLUDE):
        return False

    function = FILTERS.get(currency)

    if not function:
        return False

    return function(name)


# ============================================================
# DATE PARSING
# ============================================================

def parse_datetime(value):

    value = str(value).strip()

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

    # Keep source time naive until timezone
    # has been verified.
    return dt.replace(
        tzinfo=None
    )


# ============================================================
# ICS HELPERS
# ============================================================

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
# DATE WINDOW
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
# DOWNLOAD
# ============================================================

def fetch_country(country, currency):

    print("")
    print(
        f"Fetching ALL {country} ({currency}) events..."
    )

    # IMPORTANT:
    # NO impact=HIGH.
    #
    # We download the country calendar and decide
    # ourselves what is important.
    response = requests.get(
        API,
        params={
            "country": country,
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
# DEDUPLICATE
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
# LOG RESULTS
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
# IMPORTANT CENTRAL BANK CHECK
# ============================================================

print("")
print("==============================")
print("CENTRAL BANK CHECK")
print("==============================")


BANK_TERMS = {
    "EUR": [
        "ecb",
        "deposit facility",
        "refinancing",
    ],

    "GBP": [
        "boe",
        "official bank rate",
        "bank of england",
    ],

    "JPY": [
        "boj",
        "bank of japan",
    ],

    "CHF": [
        "snb",
        "swiss national bank",
    ],

    "CAD": [
        "boc",
        "bank of canada",
        "overnight rate",
    ],

    "AUD": [
        "rba",
        "cash rate",
        "monetary policy decision",
    ],

    "NZD": [
        "rbnz",
        "official cash rate",
        "ocr",
        "monetary policy statement",
    ],
}


for currency, terms in BANK_TERMS.items():

    bank_events = []

    for event in events:

        if event["currency"] != currency:
            continue

        text = normalize(
            event["name"]
        )

        if any(
            term in text
            for term in terms
        ):
            bank_events.append(event)

    print("")
    print(
        f"{currency} CENTRAL BANK: "
        f"{len(bank_events)}"
    )

    for event in bank_events:

        print(
            "  ",
            event["dt"],
            "-",
            event["name"]
        )


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
    "X-WR-CALDESC:Major forex market events excluding USD",
]


for event in events:

    # Still intentionally no Z.
    # We'll fix timezone after validating the
    # source timestamps.
    start = event["dt"].strftime(
        "%Y%m%dT%H%M%S"
    )

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

        "DESCRIPTION:Major market event in 30 minutes",

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
