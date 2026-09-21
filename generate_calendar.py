# ============================================================
# UK QUARTERLY GDP — OFFICIAL ONS SOURCE
#
# The general economic-calendar API can occasionally carry
# an incorrect future UK GDP date.
#
# For quarterly UK GDP, ONS is authoritative.
# ============================================================

def strip_html(value):

    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S,
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = html.unescape(
        value
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def parse_ons_release_date(text):

    match = re.search(
        (
            r"Release date:\s*"
            r"(\d{1,2}\s+"
            r"[A-Za-z]+\s+"
            r"\d{4}\s+"
            r"\d{1,2}:\d{2}"
            r"(?:am|pm))"
        ),
        text,
        flags=re.I,
    )

    if not match:
        return None

    local_dt = datetime.strptime(
        match.group(1),
        "%d %B %Y %I:%M%p",
    )

    # ONS displays release time in UK local time.
    london = ZoneInfo(
        "Europe/London"
    )

    local_dt = local_dt.replace(
        tzinfo=london
    )

    return local_dt.astimezone(
        timezone.utc
    )


def fetch_official_uk_gdp():

    quarter_slugs = [
        "januarytomarch",
        "apriltojune",
        "julytoseptember",
        "octobertodecember",
    ]

    official_events = []

    # Cover years surrounding our rolling window.
    years = range(
        start_day.year - 1,
        end_day.year + 1,
    )

    for year in years:

        for quarter in quarter_slugs:

            url = (
                "https://www.ons.gov.uk/releases/"
                "gdpfirstquarterlyestimateuk"
                f"{quarter}{year}"
            )

            try:

                response = requests.get(
                    url,
                    timeout=30,
                    headers={
                        "User-Agent":
                        "saafman-dev-forex-calendar/1.0"
                    },
                )

            except requests.RequestException:
                continue

            if response.status_code != 200:
                continue

            page_text = strip_html(
                response.text
            )

            # Make sure this really is the quarterly GDP page.
            if (
                "GDP first quarterly estimate"
                not in page_text
            ):
                continue

            dt = parse_ons_release_date(
                page_text
            )

            if dt is None:
                continue

            if not (
                range_start
                <= dt
                <= range_end
            ):
                continue

            official_events.append({
                "currency": "GBP",
                "family": "GBP_GDP",
                "title": "UK GDP First Estimate",
                "dt": dt,
                "source_names": {
                    "ONS GDP first quarterly estimate"
                },
            })

    return official_events


# Remove GBP GDP dates supplied by the general API.
events = [
    event
    for event in events
    if event["family"]
    != "GBP_GDP"
]


# Replace them with the official ONS dates.
official_uk_gdp = (
    fetch_official_uk_gdp()
)

events.extend(
    official_uk_gdp
)


print("")
print(
    "UK QUARTERLY GDP — ONS"
)

if official_uk_gdp:

    for event in sorted(
        official_uk_gdp,
        key=lambda x: x["dt"],
    ):

        print(
            " ",
            event["dt"].strftime(
                "%Y-%m-%d %H:%M UTC"
            ),
            "-",
            event["title"],
        )

else:

    print(
        "  No official ONS quarterly GDP "
        "release inside current window."
    )
