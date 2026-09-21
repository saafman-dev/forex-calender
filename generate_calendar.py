import requests
import hashlib
import re
from datetime import datetime, timezone, timedelta

API = "https://economic-calendar-api-h9hr.onrender.com/events"

# ============================================================
# SETTINGS
# ============================================================

COUNTRIES = {
    "EUR": "EUR",
    "GBR": "GBP",
    "JPN": "JPY",
    "CHE": "CHF",
    "CAN": "CAD",
    "AUS": "AUD",
    "NZL": "NZD",
}

# GitHub refreshes every 6 hours, so there is no reason
# to rely on uncertain dates a year into the future.
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
# GENERIC DATA TYPES
# ============================================================

def is_cpi(text):

    if has_any(text, [
        "producer price",
        "ppi",
        "inflation expectation",
    ]):
        return False

    return (
        re.search(r"\bcpi\b", text)
        or "inflation rate" in text
        or "consumer price index" in text
        or "hicp" in text
        or "harmonised index of consumer prices" in text
        or "harmonized index of consumer prices" in text
    )


def is_gdp(text):

    if has_any(text, [
        "gdp deflator",
        "gdp price index",
        "gdp forecast",
    ]):
        return False

    return (
        re.search(r"\bgdp\b", text)
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
# GENERAL EXCLUSIONS
# ============================================================

def globally_unwanted(text):

    return has_any(text, [
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
    ])


# ============================================================
# EVENT CLASSIFICATION
# ============================================================

def classify_event(currency, name):

    text = normalize(name)


    # ========================================================
    # CENTRAL BANKS
    # ========================================================

    # ECB
    if currency == "EUR":

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


    # Bank of England
    if currency == "GBP":

        if has_any(text, [
            "boe interest rate decision",
            "boe rate decision",
            "official bank rate",
            "bank of england interest rate",
            "boe minutes",
            "boe monetary policy report",
        ]):

            if "hearings" in text:
                return None

            return (
                "BOE_RATE",
                "BoE Rate Decision"
            )


    # Bank of Japan
    if currency == "JPY":

        # Minutes are released much later and aren't needed.
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
                "BoJ Rate Decision — time approx."
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


    # SNB
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


    # Bank of Canada
    if currency == "CAD":

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


    # RBA
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


    # RBNZ
    if currency == "NZD":

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
    # OTHER LOW-PRIORITY DATA
    # ========================================================

    if globally_unwanted(text):
        return None


    # ========================================================
    # EUR
    # ========================================================

    if currency == "EUR":

        if is_cpi(text):
            return (
                "EUR_CPI",
                "Eurozone Flash CPI"
            )

        if is_gdp(text):
            return (
                "EUR_GDP",
                "Eurozone Flash GDP"
            )

        if is_pmi(text):
            return (
                "EUR_PMI",
                "Eurozone Flash PMI"
            )

        return None


    # ========================================================
    # GBP
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
                "UK GDP First Estimate"
            )

        if is_pmi(text):
            return (
                "GBP_PMI",
                "UK Flash PMI"
            )

        if is_retail(text):
            return (
                "GBP_RETAIL",
                "UK Retail Sales"
            )

        return None


    # ========================================================
    # JPY
    # ========================================================

    if currency == "JPY":

        if is_cpi(text):

            if "tokyo" in text:
                return (
                    "JPY_TOKYO_CPI",
                    "Tokyo CPI"
                )

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
    # CHF
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
    # CAD
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
    # AUD
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
    # NZD
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
# DATE PARSING
#
# Source timestamps are UTC.
# ============================================================

def parse_datetime(value):

    value = str(value).strip()

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

    if value.endswith("Z"):
        value = (
            value[:-1]
            + "+00:00"
        )

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
# API / ICS HELPERS
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


def fold_ics_line(line):

    result = []

    current = ""
    first = True

    for char in line:

        limit = 75 if first else 74

        candidate = (
            current + char
        )

        if (
            current
            and len(
                candidate.encode(
                    "utf-8"
                )
            ) > limit
        ):

            if first:

                result.append(
                    current
                )

                first = False

            else:

                result.append(
                    " " + current
                )

            current = char

        else:
            current = candidate

    if current:

        if first:
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
        fold_ics_line(
            line
        )
    )


# ============================================================
# DATE WINDOW
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
# FETCH
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
            "Calendar update stopped."
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

        family, title = (
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

        if not (
            range_start
            <= dt
            <= range_end
        ):
            continue

        accepted.append({
            "country": country,
            "currency": currency,
            "family": family,
            "title": title,
            "source_name": str(name),
            "dt": dt,
        })

    print(
        "Accepted raw:",
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
# MERGE SAME-TIME RELEASES
#
# CPI YoY + MoM + Core -> one CPI alert.
# PMI Manufacturing + Services -> one PMI alert.
# BoE decision + minutes + MPR -> one alert.
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
        }

    groups[key][
        "source_names"
    ].add(
        event["source_name"]
    )


events = list(
    groups.values()
)


# ============================================================
# REMOVE SECONDARY / FINAL RELEASES
# ============================================================

def should_keep(event):

    family = event["family"]
    dt = event["dt"]

    text = normalize(
        " | ".join(
            sorted(
                event[
                    "source_names"
                ]
            )
        )
    )


    # --------------------------------------------------------
    # EUR FLASH PMI ONLY
    #
    # Flash is normally around the 20th-24th.
    # Final Manufacturing/Services releases are around 1st-5th.
    # --------------------------------------------------------

    if family == "EUR_PMI":

        if has_any(text, [
            "final",
            "revised",
        ]):
            return False

        return dt.day >= 15


    # --------------------------------------------------------
    # UK FLASH PMI ONLY
    # --------------------------------------------------------

    if family == "GBP_PMI":

        if has_any(text, [
            "final",
            "revised",
        ]):
            return False

        return dt.day >= 15


    # --------------------------------------------------------
    # EUROZONE FLASH CPI ONLY
    #
    # Flash CPI is normally near the end/start of month.
    # Final HICP is normally around the middle of the month.
    # --------------------------------------------------------

    if family == "EUR_CPI":

        if (
            "final" in text
            and not has_any(
                text,
                [
                    "flash",
                    "preliminary",
                ]
            )
        ):
            return False

        return (
            dt.day <= 10
            or dt.day >= 25
        )


    # --------------------------------------------------------
    # EUROZONE PRELIMINARY FLASH GDP ONLY
    # --------------------------------------------------------

    if family == "EUR_GDP":

        if has_any(text, [
            "second estimate",
            "2nd estimate",
            "third estimate",
            "3rd estimate",
            "final",
            "revised",
        ]):
            return False

        if has_any(text, [
            "preliminary flash",
            "flash estimate",
            "preliminary estimate",
        ]):
            return True

        # Safe fallback for Eurostat's end-of-month
        # preliminary GDP schedule.
        return (
            dt.day >= 25
            or dt.day <= 5
        )


    # --------------------------------------------------------
    # UK GDP:
    # ONLY FIRST QUARTERLY ESTIMATE.
    #
    # Drop monthly GDP and later quarterly national accounts.
    # --------------------------------------------------------

    if family == "GBP_GDP":

        return has_any(text, [
            "first quarterly estimate",
            "gdp first quarterly estimate",
            "preliminary estimate",
        ])


    return True


events = [
    event
    for event in events
    if should_keep(
        event
    )
]


# ============================================================
# REMOVE NEARBY DUPLICATES FROM DIFFERENT PROVIDERS
# ============================================================

def remove_nearby_duplicates(
    events,
    currency,
    family,
    hours
):

    matches = sorted(
        [
            event
            for event in events
            if (
                event["currency"]
                == currency
                and event["family"]
                == family
            )
        ],
        key=lambda x: x["dt"]
    )

    remove_ids = set()

    last_kept = None

    for event in matches:

        if last_kept is None:

            last_kept = event
            continue

        difference = (
            event["dt"]
            - last_kept["dt"]
        ).total_seconds() / 3600

        if difference <= hours:

            remove_ids.add(
                id(event)
            )

        else:

            last_kept = event

    return [
        event
        for event in events
        if id(event)
        not in remove_ids
    ]


# Occasionally the EUR feed has the same flash CPI
# from two providers a day apart.
events = remove_nearby_duplicates(
    events,
    "EUR",
    "EUR_CPI",
    72,
)


# ============================================================
# SORT
# ============================================================

events.sort(
    key=lambda event:
        event["dt"]
)


# ============================================================
# RESULTS
# ============================================================

print("")
print(
    "=============================="
)

print(
    "FINAL CLEAN EVENTS:",
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
# CENTRAL BANK CHECK
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


for line in [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//saafman-dev//Global Forex High Impact//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:🌍 Global Forex — High Impact",
    "X-WR-CALDESC:Major global forex events excluding USD",
    "X-WR-TIMEZONE:UTC",
    "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
    "X-PUBLISHED-TTL:PT6H",
]:

    add_ics_line(
        lines,
        line
    )


for event in events:

    start = event[
        "dt"
    ].strftime(
        "%Y%m%dT%H%M%SZ"
    )


    # Stable UID:
    # if the event's time changes but stays on the same date,
    # Apple updates the existing event instead of creating another.
    uid_seed = (
        f"{event['currency']}|"
        f"{event['family']}|"
        f"{event['dt'].date().isoformat()}"
    )

    uid_hash = hashlib.sha256(
        uid_seed.encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    uid = (
        uid_hash
        + "@saafman-dev.github.io"
    )


    source_names = sorted(
        event[
            "source_names"
        ]
    )

    description = (
        "Major market event. "
        "Underlying release(s): "
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
    "clean events."
)

print(
    "=============================="
)
