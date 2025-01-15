""" Christopher Mee
2024-05-11
Parse and convert date into new formats, such as day of week and 12-hour time.
"""

import datetime
import sys
from typing import Dict


def parseDate(date: str) -> Dict[str, str]:
    """Parse date.

    Args:
        date (str): Date, "YYYY-MM-DD_HHMM".

    Returns:
        Dict[str, str]: Parsed date.
    """
    try:
        parsedDate = datetime.datetime.strptime(date, "%Y-%m-%d_%H%M")
    except:
        raise ValueError(
            "Invalid date format. Please use the correct format: YYYY-MM-DD_HHMM."
        )

    return dict(
        time_12hr=parsedDate.strftime("%I:%M").upper(),
        am_pm=parsedDate.strftime("%p").upper(),
        date=parsedDate.strftime("%d"),
        day_of_week_abr=parsedDate.strftime("%a").upper(),
        month_abr=parsedDate.strftime("%b").upper(),
        year=parsedDate.strftime("%Y"),
    )


def getFormattedDate(parsedDate: Dict[str, str]) -> str:
    """Get formatted date.

    Args:
        parsedDate (Dict[str, str]): Parsed date.

    Returns:
        str: Formatted date.
    """
    return "\n".join(
        [
            f"{parsedDate['am_pm']}",
            f"{parsedDate['time_12hr']}",
            f"{parsedDate['day_of_week_abr']}",
            f"{parsedDate['month_abr']} {parsedDate['date']}, {parsedDate['year']}",
        ]
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <date>")
        sys.exit(1)

    date = sys.argv[1]
    parsedDate = parseDate(date)
    print(getFormattedDate(parsedDate))
