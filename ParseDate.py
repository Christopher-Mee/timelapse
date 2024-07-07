"""
Christopher Mee
2024-05-11
Parse date to get extra info, i.e. day of week, 12 hr time
"""

import datetime
import sys


def parseDate(date):
    """Parse date to dictionary.

    Args:
        date (str): YYYY-MM-DD_HHMM

    Returns:
        dict: dictionary containing date data
    """
    try:
        parsedDate = datetime.datetime.strptime(date, "%Y-%m-%d_%H%M")

        return dict(
            time_12hr=parsedDate.strftime("%I:%M").upper(),
            am_pm=parsedDate.strftime("%p").upper(),
            date=parsedDate.strftime("%d"),
            day_of_week_abr=parsedDate.strftime("%a").upper(),
            month_abr=parsedDate.strftime("%b").upper(),
            year=parsedDate.strftime("%Y"),
        )
    except ValueError:
        return "INVALID DATE FORMAT. PLEASE USE FORMAT: YYYY-MM-DD_HHMM"


def getFormattedDate(parsedDate):
    """Returns the parsed date formatted specific to your needs.

    Args:
        parsedDate (dict): the result from parseDate

    Returns:
        str: formatted date
    """
    tab = "    "

    return "\n".join(
        [
            f"{parsedDate['am_pm']}",
            f"{parsedDate['time_12hr']}",
            f"{parsedDate['day_of_week_abr']}{tab}{parsedDate['month_abr']} {parsedDate['date']}, {parsedDate['year']}",
        ]
    )


if __name__ == "__main__":
    # Extract date argument
    if len(sys.argv) != 2:
        print("Usage: python script.py <date>")
        sys.exit(1)

    # parse date argument
    date = sys.argv[1]
    parsedDate = parseDate(date)
    print(getFormattedDate(parsedDate))
