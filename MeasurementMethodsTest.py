"""
Christopher Mee
Python tool for comparing text measurement methods.
2024-07-01
"""

""" NOTES =====================================================================
- Determine which measurement method is accurate.
    Hint: It's none. You need to use the ASCENT font property and x, y offsets.
- Useful to compare text line attributes and visual representations.
"""

import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, cast

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# FONTS
USERNAME = os.getlogin()
HELVETICA = "C:/Users/" + USERNAME + "/Desktop/Helvetica___.ttf"
HELVETICA_BOLD = "C:/Users/" + USERNAME + "/Desktop/HelveticaBd.ttf"
ARIAL = "C:/Users/" + USERNAME + "/Desktop/arial.ttf"
ARIAL_BOLD = "C:/Users/" + USERNAME + "/Desktop/arialbd.ttf"

# STRING COMPOSITIONS
NUMBERS = list(range(48, (57 + 1)))
TIME = NUMBERS + [58]
AMPM = [65, 77, 80]
UPPERCASE = list(range(65, (90 + 1)))
LOWERCASE = list(range((65 + 32), (90 + 32 + 1)))
COMMA = [44]
DATE = UPPERCASE + COMMA + NUMBERS

# DIVIDER
DIVIDER_SIZE = 80

# TIME
TWELVE_HOUR = "%I:%M %p"
TWENTY_FOUR_HOUR = "%H:%M"

# DATE
DAY_OF_WEEK = "%a %b %d, %Y"

# PILLOW RENDER ENGINE
BINARY = "1"
ANTI_ALIASED = "L"
FONT_MODE: str = ANTI_ALIASED

# CACHE
IMG_ID = 0


class measure(Enum):
    CUSTOM_ASCII_RANGE = 0
    TIMES = 1
    AMPM = 2
    DATES = 3
    DATES_AND_DAY_OF_WEEK = 4
    DAYS = 5
    MONTHS = 6
    TAB = 7


# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.FileHandler("output.txt", mode="w"), logging.StreamHandler()],
)


def print(*args, **kwargs):
    """Overloaded print to allow both printing and logging of print."""
    message = " ".join(str(arg) for arg in args)
    logging.info(message, **kwargs)


# Add measurement methods here ################################################
def measurementMethod0(text: str, points: int, fontPath: str, debug=False) -> tuple:
    """Pillow text measurement and diagram.

    Note:
        This method uses the font ascent as height for all text. This ensures a
        consistent height for alignment purposes.

    Args:
        text (str): Text.
        points (int): Font point.
        fontPath (str): Font Path.
        debug (bool, optional): Debug measurement. Defaults to False.

    Returns:
        tuple: (`WIDTH`, `HEIGHT`), in px.
    """
    # font metrics
    font = ImageFont.truetype(fontPath, points)
    ascent, descent = font.getmetrics()
    (width, height), (offset_x, offset_y) = font.font.getsize(
        text, ANTI_ALIASED, None, None, None, None
    )
    bbox = font.getmask(text).getbbox()

    if debug:
        global IMG_ID
        L, T, R, B = range(4)

        # draw colors
        bgColor = (255, 255, 255)
        ascentTopTextColor = (237, 127, 130)
        topTextBaselineColor = (202, 229, 134)
        textColor = (0, 0, 0)
        bboxBorderColor = (255, 255, 255)
        descentColor = (134, 190, 229)
        KerningColor = (255, 250, 160)

        # draw coordinates
        ascentTopTextDrawCoords = [(0, 0), (width - 1, offset_y)]
        topTextBaselineDrawCoords = [(0, offset_y), (width - 1, ascent)]
        descentDrawCoords = [(0, ascent), (width - 1, ascent + descent - 1)]
        bboxDrawCoords = None
        lKernDrawCoords = None
        rKernDrawCoords = None
        lKernWidth = None
        rKernWidth = None
        if bbox:
            bboxDrawCoords = (
                bbox[L] + offset_x,
                bbox[T] + offset_y,
                bbox[R] + offset_x - 1,
                bbox[B] + offset_y - 1,
            )
            lKernWidth = bbox[L]
            if lKernWidth > 0:
                lKernDrawCoords = [(0, 0), (lKernWidth - 1, ascent + descent - 1)]
            rKernWidth = width - bbox[R]
            if rKernWidth > 0:
                rKernDrawCoords = [
                    (bbox[R] + offset_x, 0),
                    (bbox[R] + offset_x + rKernWidth, ascent + descent - 1),
                ]

        # draw diagram
        im = Image.new("RGB", (width + offset_x, ascent + descent), bgColor)
        draw = ImageDraw.Draw(im)
        draw.rectangle(ascentTopTextDrawCoords, ascentTopTextColor)  # red
        draw.rectangle(topTextBaselineDrawCoords, topTextBaselineColor)  # green
        draw.rectangle(descentDrawCoords, descentColor)  # blue
        if lKernDrawCoords:
            draw.rectangle(lKernDrawCoords, fill=KerningColor)  # yellow right side
        if rKernDrawCoords:
            draw.rectangle(rKernDrawCoords, fill=KerningColor)  # yellow left side
        if bboxDrawCoords:
            draw.rectangle(bboxDrawCoords, outline=bboxBorderColor)  # white
        draw.text((0, 0), text, font=font, fill=textColor)  # black
        im.save("result" + str(IMG_ID) + ".png")
        IMG_ID += 1

        # output
        print("Text:", text)
        print("W, H:", width, height)
        print("offX, offY:", offset_x, offset_y)
        print("Red height:", offset_y)
        print("Green height:", ascent - offset_y)
        print("Blue height:", descent)
        print("Black box:", bbox)
        print("Right yellow:", rKernWidth)
        print("Left yellow:", lKernWidth)

    height = ascent  # consistent height for text alignment
    return (width, height)


def getTextDimensions1(text: str, points: int, fontPath: str, debug=False) -> tuple:
    return NotImplemented


###############################################################################
def generateTimeStrs(
    start_time: str,
    end_time: str,
    input_format: str = TWELVE_HOUR,
    output_format: str = TWELVE_HOUR,
    interval_minutes: int = 1,
) -> list[str]:
    """
    Generate a list of time strings between a start time and an end time, inclusive,
    for 12-hour time inputs with AM/PM..

    Parameters:
        start_time (str): The start time as a string in the input format.
        end_time (str): The end time as a string in the input format.
        input_format (str): The format of the input time strings. Default is 'TWELVE_HOUR' (12-hour format with AM/PM).
        output_format (str): The format of the output time strings. Default is 'TWELVE_HOUR' (12-hour format with AM/PM).
        interval_minutes (int): The interval in minutes between each time in the output list. Default is 30.

    Returns:
        list[str]: A list of time strings in the specified output format.
    """
    try:
        start = datetime.strptime(start_time, input_format)
        end = datetime.strptime(end_time, input_format)
        if start > end:
            raise ValueError("Start time must be before or equal to the end time.")

        current = start
        times = []
        while current <= end:
            times.append(current.strftime(output_format))
            current += timedelta(minutes=interval_minutes)

        return times
    except ValueError as e:
        raise ValueError(f"Invalid time or format: {e}")


def generateDateStrs(
    start_date: str,
    end_date: str,
    input_format: str = "%m-%d-%Y",
    output_format: str = "%b %d, %Y",
) -> list[str]:
    """
    Generate a list of date strings between a start date and an end date, inclusive.

    Parameters:
        start_date (str): The start date as a string in the input format.
        end_date (str): The end date as a string in the input format.
        input_format (str): The format of the input date strings. Default is '%m-%d-%Y'.
        output_format (str): The format of the output date strings. Default is '%b %d, %Y'.

    Returns:
        list[str]: A list of date strings in the specified output format.
    """
    try:
        start = datetime.strptime(start_date, input_format)
        end = datetime.strptime(end_date, input_format)
        if start > end:
            raise ValueError("Start date must be before or equal to the end date.")

        current = start
        dates = []
        while current <= end:
            dates.append(current.strftime(output_format).upper())
            current += timedelta(days=1)

        return dates
    except ValueError as e:
        raise ValueError(f"Invalid date or format: {e}")


def average(lst: list[int]) -> float:
    """Calculate the average of an integer list.

    Args:
        lst (list[int]): int list.

    Returns:
        float: Average.
    """
    return sum(lst) / len(lst)


def results(
    measurementMethod: Callable[[str, int, str, bool], tuple[int, int]],
    point: int,
    fontPath: str,
    selectedRange: list[int] | list[str],
    debug: bool = False,
) -> None:
    """Print and analyze results from a text measurement method. Only works for ascii ranges.

    Note:
        Works with list of ascii characters and strings.

    Args:
        measurementMethod (Callable[[str, int, str, bool], tuple[int, int]]): `getTextDimensionX()`
        point (int): Font point.
        fontPath (str): Font path.
        selectedRange (list[int]): Ascii range (non consecutive) or text composition.
        debug (bool, optional): Print debug information. Defaults to False.
    """
    resultsX = []
    resultsY = []

    if isinstance(selectedRange[0], int):
        selectedRange = cast(list[int], selectedRange)
        for ascii in selectedRange:
            char = chr(ascii)
            result = measurementMethod(char, point, fontPath, debug)
            print(str(ascii) + " (" + char + ") : " + str(result))
            resultsX.append(result[0])
            resultsY.append(result[1])
            print(customDivider(DIVIDER_SIZE // 2))
    elif isinstance(selectedRange[0], str):
        selectedRange = cast(list[str], selectedRange)
        for string in selectedRange:
            result = measurementMethod(string, point, fontPath, debug)
            print(string + " : " + str(result))
            resultsX.append(result[0])
            resultsY.append(result[1])
            print(customDivider(DIVIDER_SIZE // 2))

    print(
        "Max W: "
        + str(max(resultsX))
        + "; Min W: "
        + str(min(resultsX))
        + "; Range W: "
        + str(max(resultsX) - min(resultsX))
        + "; Avg W: "
        + str(np.round(average(resultsX), decimals=2))
    )
    print(
        "Max H: "
        + str(max(resultsY))
        + "; Min H: "
        + str(min(resultsY))
        + "; Range H: "
        + str(max(resultsY) - min(resultsY))
        + "; Avg H: "
        + str(np.round(average(resultsY), decimals=2))
    )


def customDivider(length: int, str: str | None = None) -> str:
    """Generate a divider string with your string inserted into the middle.

    Args:
        size (int): Length.
        str (str, optional): Inserted string. Defaults to "".

    Raises:
        ValueError: String too large for divider size.

    Returns:
        str: Divider string.
    """
    if str:
        if length < len(str) + 4:
            raise ValueError("Divider length is too small for the inserted string.")

        # Calculate the length of '=' on each side
        remaining_space = length - len(str) - 2  # -2 for spaces around the string
        left_side = remaining_space // 2
        right_side = remaining_space - left_side

        # Construct the divider
        divider = "=" * left_side + f" {str} " + "=" * right_side
    else:
        # No string provided, just return '=' repeated to the length
        divider = "=" * length

    return divider


if __name__ == "__main__":
    DAY_STRS = [
        "MON",
        "TUE",
        "WED",
        "THU",
        "FRI",
        "SAT",
        "SUN",
    ]
    MONTH_STRS = [
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    ]
    AMPM_STRS = [
        "AM",
        "PM",
    ]
    SPACE = " "
    DIVIDER = customDivider(DIVIDER_SIZE // 2)

    methods = [
        measurementMethod0,
    ]
    methodIndex = 0
    fontFile = ARIAL_BOLD
    fontPoint = 36
    debug = True  # print debug info and render text image diagrams

    """↓↓↓ SET MEASUREMENT TYPE HERE ↓↓↓"""
    measurementType = measure.MONTHS

    for method in methods[:]:  # To limit methods tested, use a subset here.
        print(customDivider(DIVIDER_SIZE, method.__name__))
        match measurementType:
            case measure.CUSTOM_ASCII_RANGE:
                ascii_range = NUMBERS
                results(method, fontPoint, fontFile, ascii_range, debug)

            case measure.TIMES:
                start = "9:59 AM"
                end = "12:00 PM"
                times = generateTimeStrs(start, end)
                results(method, fontPoint, fontFile, times, debug)

            case measure.AMPM:
                results(method, fontPoint, fontFile, AMPM_STRS, debug)

            case measure.DATES:
                start = "2-9-2017"
                end = "2-28-2017"
                dates = generateDateStrs(start, end)
                results(method, fontPoint, fontFile, dates, debug)

            case measure.DATES_AND_DAY_OF_WEEK:
                start = "2-9-2017"
                end = "2-28-2017"
                dates = generateDateStrs(start, end, output_format=DAY_OF_WEEK)
                results(method, fontPoint, fontFile, dates, debug)

            case measure.DAYS:
                results(method, fontPoint, fontFile, DAY_STRS, debug)

            case measure.MONTHS:
                results(method, fontPoint, fontFile, MONTH_STRS, debug)

            case measure.TAB:
                tabSize = 4  # in spaces
                tab = SPACE * tabSize
                results(method, fontPoint, fontFile, [tab], debug)
