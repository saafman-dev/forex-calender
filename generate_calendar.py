import requests
import hashlib
import re
from datetime import datetime, timezone, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# SETTINGS
# ============================================================

# USD deliberately excluded:
# AIO Economic Calendar already covers USD.
COUNTRIES = {
    "EUR": "EUR",
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",
}

# We don't need unreliable events a year in advance.
# GitHub refreshes this feed every 6 hours.
LOOKBACK_DAYS = 7
LOOKAHEAD_DAYS = 60


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(value):
    text = str(value or "").lower()

    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def has_any(text, terms):
    return any(
        term in text
        for term in terms
    )


# ============================================================
# GENERIC EVENT TYPES
# ============================================================

def is_cpi(text):
    if has_any(text, [
        "producer price",
        "ppi",
        "inflation expectations",
        "inflation expectation",
    ]):
        return False

    return (
        re.search(r"\bcpi\b", text) is not None
        or "inflation rate" in text
        or "consumer price index" in text
        or "hicp" in text
        or "harmonised index of consumer prices" in text
        or "harmonized index of consumer prices" in text
    )


def is_gdp(text):
    if has_any(text, [
        "gdp deflator",
        "gdp price",
        "gdp forecast",
        "gdp estimate",
    ]):
        return False

    if re.search(
        r"\b(2nd|second|3rd|third)\s+(est|estimate)",
        text
    ):
        return False

    return (
        re.search(r"\bgdp\b", text) is not None
        or "gross domestic product" in text
    )


def is_pmi(text):
    return has_any(text, [
        "manufacturing pmi",
        "services pmi",
        "composite pmi",
    ])


def is_retail(text):
    return text.startswith(
        "retail sales"
    )


# ============================================================
# UNWANTED EVENTS
# ============================================================

def globally_unwanted(text):

    unwanted = [
        "speech",
        "speaks",
        "testimony",
        "hearings",
        "consumer confidence",
        "business confidence",
        "economic sentiment",
        "bond auction",
        "bill auction",
        "trade balance",
        "current account",
        "industrial production",
        "factory orders",
        "housing starts",
        "building permits",
        "house price",
        "mortgage",
        "money supply",
        "credit card",
        "tourist",
        "tourism",
        "vehicle sales",
        "car registrations",
        "monthly report",
        "bulletin",
    ]

    return has_any(
        text,
        unwanted
    )


# ============================================================
# EVENT CLASSIFICATION
#
# Return:
#
#   (family, clean calendar title)
#
# or None when event should not be included.
# ============================================================

def classify_event(currency, name):

    text = normalize(name)


    # ========================================================
    # EUR / ECB
    # ========================================================

    if currency == "EUR":

        # ECB press conference deserves its own alert.
        if (
            "ecb press conference" in text
            or (
                "press conference" in text
                and "ecb" in text
            )
        ):
            return (
                "ECB_PRESS",
                "ECB Press Conference"
            )

        # Merge all simultaneous ECB rate rows.
        if has_any(text, [
            "ecb interest rate decision",
            "ecb rate decision",
            "ecb monetary policy decision",
            "monetary policy decision",
            "deposit facility rate",
            "main refinancing rate",
            "main refinancing operations rate",
            "marginal lending facility rate",
        ]):
            return (
                "ECB_RATE",
                "ECB Rate Decision"
            )


    # ========================================================
    # GBP / BANK OF ENGLAND
    # ========================================================

    if currency == "GBP":

        # Not important enough for this calendar.
        if "hearings" in text:
            return None

        # Decision + minutes + MPR become ONE alert.
        if has_any(text, [
            "boe interest rate decision",
            "boe rate decision",
            "official bank rate",
            "bank of england interest rate",
            "boe minutes",
            "boe monetary policy report",
        ]):
            return (
                "BOE_RATE",
                "BoE Rate Decision"
            )


    # ========================================================
    # JPY / BANK OF JAPAN
    # ========================================================

    if currency == "JPY":

        # Minutes weeks later are not top-tier.
        if "minutes" in text:
            return None

        if has_any(text, [
            "boj interest rate decision",
            "boj rate decision",
            "bank of japan interest rate",
            "boj monetary policy statement",
            "bank of japan monetary policy statement",
        ]):
            return (
                "BOJ_RATE",
                "BoJ Rate Decision"
            )

        if (
            "press conference" in text
            and has_any(text, [
                "boj",
                "bank of japan",
            ])
        ):
            return (
                "BOJ_PRESS",
                "BoJ Press Conference"
            )


    # ========================================================
    # CHF / SNB
    # ========================================================

    if currency == "CHF":

        if has_any(text, [
            "snb interest rate decision",
            "snb rate decision",
            "snb policy rate",
            "swiss national bank interest rate",
        ]):
            return (
                "SNB_RATE",
                "SNB Rate Decision"
            )

        if (
            "press conference" in text
            and has_any(text, [
                "snb",
                "swiss national bank",
            ])
        ):
            return (
                "SNB_PRESS",
                "SNB Press Conference"
            )


    # ========================================================
    # CAD / BANK OF CANADA
    # ========================================================

    if currency == "CAD":

        # Decision + MPR become ONE alert.
        if has_any(text, [
            "boc interest rate decision",
            "boc rate decision",
            "bank of canada interest rate",
            "overnight rate",
            "boc monetary policy report",
            "bank of canada monetary policy report",
        ]):
            return (
                "BOC_RATE",
                "BoC Rate Decision"
            )

        if (
            "press conference" in text
            and has_any(text, [
                "boc",
                "bank of canada",
            ])
        ):
            return (
                "BOC_PRESS",
                "BoC Press Conference"
            )


    # ========================================================
    # AUD / RBA
    # ========================================================

    if currency == "AUD":

        if has_any(text, [
            "rba interest rate decision",
            "rba rate decision",
            "rba cash rate",
            "cash rate target",
            "reserve bank of australia interest rate",
            "monetary policy decision",
        ]):
            return (
                "RBA_RATE",
                "RBA Rate Decision"
            )

        if (
            "rba" in text
            and has_any(text, [
                "press conference",
                "media conference",
            ])
        ):
            return (
                "RBA_PRESS",
                "RBA Press Conference"
            )


    # ========================================================
    # NZD / RBNZ
    # ========================================================

    if currency == "NZD":

        # Decision + MPS become ONE alert.
        if has_any(text, [
            "rbnz interest rate decision",
            "rbnz rate decision",
            "official cash rate",
            "rbnz monetary policy statement",
            "reserve bank of new zealand interest rate",
        ]):
            return (
                "RBNZ_RATE",
                "RBNZ Rate Decision"
            )

        # Avoid matching unrelated words containing "ocr".
        if re.search(
            r"\bocr\b",
            text
        ):
            return (
                "RBNZ_RATE",
                "RBNZ Rate Decision"
            )

        if (
            "press conference" in text
            and has_any(text, [
                "rbnz",
                "reserve bank of new zealand",
            ])
        ):
            return (
                "RBNZ_PRESS",
                "RBNZ Press Conference"
            )


    # ========================================================
    # DROP GENERIC LOW-PRIORITY MATERIAL
    # ========================================================

    if globally_unwanted(text):
        return None


    # ========================================================
    # EUR MACRO
    # ========================================================

    if currency == "EUR":

        if is_cpi(text):
            return (
                "EUR_CPI",
                "Eurozone CPI"
            )

        if is_gdp(text):
            return (
                "EUR_GDP",
                "Eurozone GDP"
            )

        # Manufacturing / services / composite at same time
        # will be collapsed to one PMI event.
        if is_pmi(text):
            return (
                "EUR_PMI",
                "Eurozone PMI"
            )

        return None


    # ========================================================
    # GBP MACRO
    # ========================================================

    if currency == "GBP":

        if is_cpi(text):
            return (
                "GBP_CPI",
                "UK CPI"
            )

        if has_any(text, [
            "claimant count change",
            "employment change",
            "unemployment rate",
            "average earnings",
            "average weekly earnings",
        ]):
            return (
                "GBP_JOBS",
                "UK Labour Market"
            )

        if is_gdp(text):
            return (
                "GBP_GDP",
                "UK GDP"
            )

        if is_pmi(text):
            return (
                "GBP_PMI",
                "UK PMI"
            )

        if is_retail(text):
            return (
                "GBP_RETAIL",
                "UK Retail Sales"
            )

        return None


    # ========================================================
    # JPY MACRO
    # ========================================================

    if currency == "JPY":

        if is_cpi(text):

            if "tokyo" in text:
                return (
                    "JPY_TOKYO_CPI",
                    "Tokyo CPI"
                )

            if (
                "national" in text
                or "japan" in text
                or "cpi" in text
            ):
                return (
                    "JPY_CPI",
                    "Japan CPI"
                )

        if is_gdp(text):
            return (
                "JPY_GDP",
                "Japan GDP"
            )

        return None


    # ========================================================
    # CHF MACRO
    # ========================================================

    if currency == "CHF":

        if is_cpi(text):
            return (
                "CHF_CPI",
                "Swiss CPI"
            )

        if is_gdp(text):
            return (
                "CHF_GDP",
                "Swiss GDP"
            )

        return None


    # ========================================================
    # CAD MACRO
    # ========================================================

    if currency == "CAD":

        if is_cpi(text):
            return (
                "CAD_CPI",
                "Canada CPI"
            )

        if has_any(text, [
            "employment change",
            "unemployment rate",
        ]):
            return (
                "CAD_JOBS",
                "Canada Jobs"
            )

        if is_gdp(text):
            return (
                "CAD_GDP",
                "Canada GDP"
            )

        if is_retail(text):
            return (
                "CAD_RETAIL",
                "Canada Retail Sales"
            )

        return None


    # ========================================================
    # AUD MACRO
    # ========================================================

    if currency == "AUD":

        if is_cpi(text):
            return (
                "AUD_CPI",
                "Australia CPI"
            )

        if has_any(text, [
            "employment change",
            "unemployment rate",
        ]):
            return (
                "AUD_JOBS",
                "Australia Jobs"
            )

        if is_gdp(text):
            return (
                "AUD_GDP",
                "Australia GDP"
            )

        return None


    # ========================================================
    # NZD MACRO
    # ========================================================

    if currency == "NZD":

        if is_cpi(text):
            return (
                "NZD_CPI",
                "New Zealand CPI"
            )

        if has_any(text, [
            "employment change",
            "unemployment rate",
        ]):
            return (
                "NZD_JOBS",
                "New Zealand Jobs"
            )

        if is_gdp(text):
            return (
                "NZD_GDP",
                "New Zealand GDP"
            )

        return None


    return None


# ============================================================
# SOURCE DATE PARSING
#
# Near-term central-bank dates have been cross-checked against
# official schedules. Source timestamps are UTC.
# ============================================================

def parse_datetime(value):

    value = str(value).strip()

    # Source format:
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
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    dt = datetime.fromisoformat(
        value
    )

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    )


# ============================================================
# API HELPERS
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
            value = data.get(key)

            if isinstance(
                value,
                list
            ):
                return value

    return []


# ============================================================
# ICS HELPERS
# ============================================================

def escape_ics(value):

    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


# RFC 5545 recommends lines no longer than 75 octets.
def fold_ics_line(line):

    result = []

    current = ""
    first_line = True

    for char in line:

        limit = (
            75
            if first_line
            else 74
        )

        candidate = (
            current + char
        )

        if (
            current
            and len(
                candidate.encode("utf-8")
            ) > limit
        ):

            if first_line:
                result.append(
                    current
                )

                first_line = False

            else:
                result.append(
                    " " + current
                )

            current = char

        else:
            current = candidate

    if current:

        if first_line:
            result.append(
                current
            )

        else:
            result.append(
                " " + current
            )

    return result


def add_ics_line(lines, line):

    lines.extend(
        fold_ics_line(line)
    )


# ============================================================
# ROLLING DATE WINDOW
# ============================================================

now = datetime.now(
    timezone.utc
)

start_day = (
    now
    - timedelta(
        days=LOOKBACK_DAYS
    )
).date()

end_day = (
    now
    + timedelta(
        days=LOOKAHEAD_DAYS
    )
).date()


start_string = (
    start_day.isoformat()
)

end_string = (
    end_day.isoformat()
)


range_start = datetime(
    start_day.year,
    start_day.month,
    start_day.day,
    tzinfo=timezone.utc,
)

range_end = datetime(
    end_day.year,
    end_day.month,
    end_day.day,
    23,
    59,
    59,
    tzinfo=timezone.utc,
)


print(
    "Calendar window:",
    start_string,
    "to",
    end_string,
)


# ============================================================
# FETCH RAW EVENTS
# ============================================================

def fetch_country(
    country,
    currency
):

    print("")
    print(
        f"Fetching {country} "
        f"({currency})..."
    )

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
        "HTTP:",
        response.status_code
    )

    response.raise_for_status()

    rows = extract_events(
        response.json()
    )

    if not rows:
        raise RuntimeError(
            f"{country} returned zero rows. "
            "Refusing to publish an incomplete calendar."
        )

    print(
        "Raw rows:",
        len(rows)
    )

    accepted = []

    for row in rows:

        if not isinstance(
            row,
            dict
        ):
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
            or row.get("Date")
            or row.get("date")
        )

        if (
            not name
            or not start
        ):
            continue

        classification = (
            classify_event(
                currency,
                name
            )
        )

        if not classification:
            continue

        family, clean_title = (
            classification
        )

        try:
            dt = parse_datetime(
                start
            )

        except Exception as error:

            print(
                "Bad date:",
                start,
                error
            )

            continue

        # Protect against the API ignoring date parameters.
        if not (
            range_start
            <= dt
            <= range_end
        ):
            continue

        source_id = (
            row.get("Id")
            or row.get("id")
            or ""
        )

        accepted.append({
            "country": country,
            "currency": currency,
            "family": family,
            "title": clean_title,
            "source_name": str(name),
            "source_id": str(source_id),
            "dt": dt,
        })

    print(
        "Accepted raw events:",
        len(accepted)
    )

    return accepted


raw_events = []

for country, currency in COUNTRIES.items():

    raw_events.extend(
        fetch_country(
            country,
            currency
        )
    )


# ============================================================
# MERGE SIMULTANEOUS DUPLICATES
#
# Examples:
#
# BoE Rate Decision + Minutes + MPR
#   -> ONE BoE Rate Decision event
#
# CPI MoM + CPI YoY + Core CPI
#   -> ONE CPI event
#
# Manufacturing + Services PMI
#   -> ONE PMI event
# ============================================================

groups = {}


for event in raw_events:

    key = (
        event["currency"],
        event["family"],
        event["dt"],
    )

    if key not in groups:

        groups[key] = {
            "currency": event["currency"],
            "family": event["family"],
            "title": event["title"],
            "dt": event["dt"],
            "source_names": set(),
            "source_ids": set(),
        }

    groups[key][
        "source_names"
    ].add(
        event["source_name"]
    )

    if event["source_id"]:

        groups[key][
            "source_ids"
        ].add(
            event["source_id"]
        )


events = list(
    groups.values()
)

events.sort(
    key=lambda event:
        event["dt"]
)


# ============================================================
# OUTPUT CHECKS
# ============================================================

print("")
print(
    "=============================="
)
print(
    "FINAL MERGED EVENTS:",
    len(events)
)
print(
    "=============================="
)


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
        if event["currency"]
        == currency
    ]

    print("")
    print(
        f"{currency}: "
        f"{len(currency_events)}"
    )

    for event in currency_events:

        print(
            " ",
            event["dt"].strftime(
                "%Y-%m-%d %H:%M UTC"
            ),
            "-",
            event["title"]
        )


# ============================================================
# CENTRAL BANK SANITY CHECK
# ============================================================

print("")
print(
    "=============================="
)
print(
    "CENTRAL BANK CHECK"
)
print(
    "=============================="
)


for currency in [
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
]:

    bank_events = [
        event
        for event in events
        if (
            event["currency"]
            == currency
            and (
                "_RATE"
                in event["family"]
                or "_PRESS"
                in event["family"]
            )
        )
    ]

    print("")
    print(
        f"{currency} CENTRAL BANK: "
        f"{len(bank_events)}"
    )

    for event in bank_events:

        print(
            " ",
            event["dt"].strftime(
                "%Y-%m-%d %H:%M UTC"
            ),
            "-",
            event["title"]
        )


# ============================================================
# BUILD ICS
# ============================================================

dtstamp = now.strftime(
    "%Y%m%dT%H%M%SZ"
)


lines = []

add_ics_line(
    lines,
    "BEGIN:VCALENDAR"
)

add_ics_line(
    lines,
    "VERSION:2.0"
)

add_ics_line(
    lines,
    "PRODID:-//saafman-dev//Global Forex High Impact//EN"
)

add_ics_line(
    lines,
    "CALSCALE:GREGORIAN"
)

add_ics_line(
    lines,
    "METHOD:PUBLISH"
)

add_ics_line(
    lines,
    "X-WR-CALNAME:🌍 Global Forex — High Impact"
)

add_ics_line(
    lines,
    "X-WR-CALDESC:Major forex market events excluding USD"
)

add_ics_line(
    lines,
    "REFRESH-INTERVAL;VALUE=DURATION:PT6H"
)

add_ics_line(
    lines,
    "X-PUBLISHED-TTL:PT6H"
)


for event in events:

    start = event[
        "dt"
    ].strftime(
        "%Y%m%dT%H%M%SZ"
    )

    # Prefer a stable source ID.
    ids = sorted(
        event["source_ids"]
    )

    if ids:

        uid_seed = (
            f"{event['currency']}|"
            f"{event['family']}|"
            f"{ids[0]}"
        )

    else:

        uid_seed = (
            f"{event['currency']}|"
            f"{event['family']}|"
            f"{event['dt'].isoformat()}"
        )

    uid_hash = hashlib.sha256(
        uid_seed.encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    uid = (
        f"{uid_hash}"
        "@saafman-dev.github.io"
    )


    source_names = sorted(
        event["source_names"]
    )

    description = (
        "Major market event. "
        "Underlying releases: "
        + "; ".join(
            source_names
        )
    )


    add_ics_line(
        lines,
        "BEGIN:VEVENT"
    )

    add_ics_line(
        lines,
        f"UID:{uid}"
    )

    add_ics_line(
        lines,
        f"DTSTAMP:{dtstamp}"
    )

    add_ics_line(
        lines,
        f"LAST-MODIFIED:{dtstamp}"
    )

    add_ics_line(
        lines,
        f"DTSTART:{start}"
    )

    # Small visible duration in Apple Calendar.
    add_ics_line(
        lines,
        "DURATION:PT5M"
    )

    add_ics_line(
        lines,
        (
            f"SUMMARY:🔴 "
            f"{event['currency']} — "
            f"{escape_ics(event['title'])}"
        )
    )

    add_ics_line(
        lines,
        (
            "DESCRIPTION:"
            + escape_ics(
                description
            )
        )
    )

    add_ics_line(
        lines,
        "STATUS:CONFIRMED"
    )

    add_ics_line(
        lines,
        "TRANSP:TRANSPARENT"
    )

    add_ics_line(
        lines,
        "BEGIN:VALARM"
    )

    add_ics_line(
        lines,
        "TRIGGER:-PT30M"
    )

    add_ics_line(
        lines,
        "ACTION:DISPLAY"
    )

    add_ics_line(
        lines,
        "DESCRIPTION:Major market event in 30 minutes"
    )

    add_ics_line(
        lines,
        "END:VALARM"
    )

    add_ics_line(
        lines,
        "END:VEVENT"
    )


add_ics_line(
    lines,
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


print("")
print(
    "=============================="
)
print(
    "Calendar created with",
    len(events),
    "merged events."
)
print(
    "=============================="
)
