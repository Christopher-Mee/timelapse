"""
Christopher Mee
2024-07-01
Draw a date and time overlay on images.

== KNOWN ISSUES ===============================================================

== HIGH PRIORITY ==============================================================
-Find the font size for layouts 1 and 2
    -Debug tabs not making line longer

-Add setting for tab size

-Add size modifier, keeps font point ratio, while increases or decreases overlay size

-Fix arial font ex: 11 am is different than other hours.

== LOW PRIORITY ===============================================================
-Inaccurate line composition large text inaccurate margin. ex AMPM, splitter
    ->Add index and composition to cache when using splitter.
      ->Fix border logic; Subtract TrueHeight instead of offL/Y

-If text size is too large, the descender can overlap the TextLine beneath it.
    Solution 1: Make the leading larger, or give small text and large text 
    independent leading sizes.
    Solution 2: Divide descender by leading to get a dynamic leading size. 
    Could also do a percentage. Ex. descender is 50% overlapping the leading, 
    push it back so its only 30% overlapping. Commas should be overlapping the 
    leading.

- If text size is too large, having a small margin will cause the descender to 
be drawn off screen.
    Solution: Bottom margin should be changed to follow the leading size.

== WARNING ====================================================================
    1) Not all fonts are supported. If your selected font isn't being displayed 
properly, find a different font. (FFmpeg cannot properly render certain font 
files, resulting in text being drawn inconsistently.)

    2) If you want faster rendering, use FFmpeg. FFmpeg is less accurate than 
pillow. FFmpeg uses the same font library as pillow, but must have different 
attributes internally, like height and width. These values cant be accessed by 
this program.

    3) If you want different line composition for date and ampm, then you need 
to change the way the cache works. Example being, setting a lower case ampm 
will cause the cache to return the date leading offset which is uppercase.

    Line composition means taking the characters from a TextLine and checking 
them against a range like upper, lower, and number. Then using the combined 
range to calculate the leading offset.

    Leading offset will affect leading and margin sizing.

== Starter Guide for Drawing Text =============================================
    Width and height are helpful but dont tell the full story. You need to 
indent by the x and y offsets to draw text accurately. Then you can go further 
and use the bounding box (bbox) to remove preceding and trailing whitespace 
called kerning.

    To draw the next line, you need to subtract the prev offset Y from the 
prev lines Y pos to get a new baseline. The baseline will be a consistent 
anchor point, but leaves a large whitespace gap above the prev text line. This 
will cause your leading to be inaccurate and look bad. My approach to solving 
this problem, is to brute-force parse the font file to determine and minimize 
the Y offset. And in doing so, creating a new leading offset, which minimizes 
whitespace, while maintaining a consistent anchor point.

== Diagram ====================================================================
    *
    *
    *
    OFFSET_Y or OFFSET_LEADING
    ASCENDER
    TEXT
    BASELINE ________________
    DESCENDER
    LEADING
    OFFSET_Y or OFFSET_LEADING
    ASCENDER
    TEXT
    BASELINE ________________
    DESCENDER
    MARGIN

== Resources ==================================================================
https://ffmpeg.org/ffmpeg-filters.html#drawtext
https://stackoverflow.com/a/68664685
https://adamj.eu/tech/2021/07/06/python-type-hints-how-to-use-typing-cast/
https://pillow.readthedocs.io/en/stable/
https://stackoverflow.com/questions/51601103
https://github.com/python-pillow/Pillow/pull/7142
"""

import glob
import math
import os
import re
import sys
import threading
import time
from enum import Enum
from typing import cast, Dict

from PIL import Image

import ParseDate
from TextLine import TextLine, RenderEngine, Resize, TextMetric, FindMetric


# ENUM
class Overlay(Enum):
    """Overlay design.

    See also:
        `setPosition()`
    """

    DEFAULT = 0
    LAYOUT_1 = 1
    LAYOUT_2 = 2
    LAYOUT_3 = 3


class Location(Enum):
    """Overlay location.

    See also:
        `shiftPosition()`
    """

    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3


class FindLine(Enum):
    """Search mode.

    See also:
        `search()`
    """

    HIGHEST = 0
    LOWEST = 1
    LEFTMOST = 2
    RIGHTMOST = 3


# FINAL
SCRIPT_NAME: str = os.path.basename(__file__)
USERNAME: str = os.getlogin()

# TEXTLINE INDEXES
AMPM, TIME, DAY, DATE = range(4)

# OVERLAY CONSTANTS
DAYS_OF_WEEK = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
MONTHS = [
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

# == FONT =====================================================================
HELVETICA: str = "C:/Users/" + USERNAME + "/Desktop/Helvetica___.ttf"
HELVETICA_BOLD: str = "C:/Users/" + USERNAME + "/Desktop/HelveticaBd.ttf"

ARIAL = "C:/Users/" + USERNAME + "/Desktop/arial.ttf"
ARIAL_BOLD = "C:/Users/" + USERNAME + "/Desktop/arialbd.ttf"

# == SETTINGS =================================================================
RENDER_ENGINE: RenderEngine = RenderEngine.PILLOW

# == RECOMMENDED LAYOUT SETTINGS =================
# L1 - 2:1    -  72, 36; LEADING, MARGIN - 10, 10
# L2 - 2:1    -  72, 36; LEADING, MARGIN - 10, 10
# L3 - 127:30 - 127, 30; LEADING, MARGIN - 15, 10
# ================================================

# Supported color - "#RRGGBBAA"

# date, ampm str
SMALL_FONT: str = HELVETICA_BOLD
SMALL_FONT_POINT: int = 30
SMALL_FONT_COLOR: str = "#FF00FF80" #F0F0F0"

# time str
LARGE_FONT: str = HELVETICA
LARGE_FONT_POINT: int = 127
LARGE_FONT_COLOR: str = "#FF00FF80"

# overlay
LAYOUT: Overlay = Overlay.LAYOUT_3
LOCATION: Location = Location.BOTTOM_RIGHT
MARGIN: float = 10
LEADING: float = 15

# border
BORDER: bool = True
BORDER_COLOR: str = "#00000040"

# modifier
LEADING_ZERO: bool = True
STATIC_DATE: bool = False
# =============================================================================

# CACHE
LEADING_OFFSETS: list[tuple[TextLine, int]] = []
EXTEND_RESULTS: list[tuple[TextLine, TextLine, float, int, tuple[str, float]]] = []
RESIZE_RESULTS: list[
    tuple[
        TextLine, TextLine, Resize, int, tuple[tuple[float, float], tuple[float, float]]
    ]
] = []
SEARCH_RESULTS: Dict[FindLine, int] = {}
MIN_TABS: list[tuple[TextLine, list[str], int]] = []

# RENDER THREADING
IMAGES_RENDERED: int = 0
LOCK: threading.Lock = threading.Lock()
STOP_EVENT = threading.Event()

# DEBUG
TAB_COUNT = 0


def search(linesToDraw: list[TextLine], mode: FindLine) -> TextLine:
    """Find TextLine from list of TextLines to draw. Result is cached.

    NOTE: Cache must be cleared if new TextLines are added to the list.

    Args:
        linesToDraw (list[TextLine]): TextLines to draw.
        mode (FindLine): Find mode (`HIGHEST`, `LOWEST`, `LEFTMOST`, `RIGHTMOST`).

    Returns:
        TextLine: Result.
    """
    MAX, MIN = sys.maxsize, -sys.maxsize - 1
    GREATER_THAN, LESS_THAN = 1, -1
    resultIndex = 0

    if mode in SEARCH_RESULTS:
        return linesToDraw[SEARCH_RESULTS[mode]]
    elif len(linesToDraw) == 1:
        return linesToDraw[resultIndex]
    elif mode == FindLine.LOWEST or mode == FindLine.RIGHTMOST:
        compareOperation = GREATER_THAN
        resultValue = MIN
    else:
        compareOperation = LESS_THAN
        resultValue = MAX

    for i, line in enumerate(linesToDraw):
        match mode:
            case FindLine.HIGHEST:
                toCompare = line.getPos()[TextLine.Y] + getLeadingOffset(line)

            case FindLine.LOWEST:
                toCompare = line.getPos()[TextLine.Y] + getLeadingOffset(line)

            case FindLine.LEFTMOST:
                toCompare = line.getPos()[TextLine.X] + TextLine.getExcessKerning(
                    line, TextMetric.LEFT_KERNING
                )

            case FindLine.RIGHTMOST:
                toCompare = (
                    line.getPos()[TextLine.X]
                    + line.getSize()[TextLine.WIDTH]
                    - TextLine.getExcessKerning(line, TextMetric.RIGHT_KERNING)
                )

            case _:  # default
                raise ValueError("Invalid FindLine mode.")

        # comparison
        if (toCompare * compareOperation) > (resultValue * compareOperation):
            resultIndex = i
            resultValue = toCompare

    SEARCH_RESULTS[mode] = resultIndex
    return linesToDraw[resultIndex]


def getLeadingOffset(toDraw: TextLine) -> int:
    """Get leading offset. Result is cached.

    \nNotes:
        -TLDR; The leading offset takes the smallest `OFFSET_Y` from the\n
            TextLine (using its predicted composition), then subtracts the\n
            current `OFFSET_Y` to determine the required whitespace needed to\n
            maintain a consistent leading baseline.\n

        -The ascender is the font style's maximum possible height above the\n
            baseline, causing undesired whitespace.\n

        -`OFFSET_Y` is the indentation from the ascender, indicating where the\n
            TextLine should be drawn to ensure accuracy.\n

        -The smallest `OFFSET_Y` minimizes excess whitespace. Since no other\n
            characters in the TextLine are taller than the character with the\n
            smallest `OFFSET_Y`, whitespace above it can be disregarded.\n

        -The leading offset is created to help draw text with a larger\n
            `OFFSET_Y` than the text with the smallest `OFFSET_Y`. The leading\n
            offset adds whitespace to the current `OFFSET_Y` to match the\n
            smallest OFFSET_Y. This ensures a TextLine has a consistent\n
            leading baseline, even when the text content differ.\n

    \nSee also:
        `TextLine.getSmallestOffY()`

    \nArgs:
        toDraw (TextLine): TextLine to draw.

    Returns:
        int: Leading offset.
    """
    global LEADING_OFFSETS
    smallestOffY = cast(int, None)

    TO_DRAW, RESULT = 0, 1
    i = len(LEADING_OFFSETS) - 1  # Read cache from newest.
    while not smallestOffY and i > -1:
        result = LEADING_OFFSETS[i]
        if toDraw.compareStyle(result[TO_DRAW]):
            smallestOffY = result[RESULT]

        i -= 1

    if not smallestOffY:
        toDrawCopy = TextLine.copy(toDraw)
        smallestOffY = TextLine.searchMetric(
            toDraw, FindMetric.SMALLEST, TextMetric.Y_OFFSET
        )

        LEADING_OFFSETS += [(toDrawCopy, smallestOffY)]

    return smallestOffY - toDraw.getOffset()[TextLine.OFFSET_Y]


def resizeTextLine(
    toResize: TextLine, toCompare: TextLine, resizeMode: Resize
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Resize TextLine to match an anchor TextLine. Results are cached.\n

    Note:
        The cache returns identical results for similar parameters.

        toResize should not change style, cache result once per set of non-similar parameters.

        If toCompare (anchor) changes width, cache will return invalid result.

    See also:
        `TextLine.resize()`

    Args:
        toResize (TextLine): TextLine to resize.
        toCompare (TextLine): TextLine to compare.
        resizeMode (Resize): Resize mode (`GROW`, `SHRINK`).

    Returns:
        tuple[tuple[float, float], tuple[float, float]]: Difference between original and new size, \n
                (widthDif, HeightDif), (xOffDif, yOffDif).
    """
    global RESIZE_RESULTS

    sizeDif = (cast(float, None), cast(float, None))
    offDif = (cast(float, None), cast(float, None))
    sizeDif = (sizeDif, offDif)
    newFontPoint = cast(int, None)

    TO_RESIZE, TO_COMPARE, RESIZE_MODE, NEW_FONT_POINT, SIZE_DIF = 0, 1, 2, 3, 4
    i = len(RESIZE_RESULTS) - 1  # Read cache from newest.
    while not newFontPoint and i > -1:
        result = RESIZE_RESULTS[i]
        if (
            TextLine.compareStyle(toResize, result[TO_RESIZE])
            and TextLine.compareStyle(toCompare, result[TO_COMPARE])
            and resizeMode == result[RESIZE_MODE]
        ):
            newFontPoint = result[NEW_FONT_POINT]
            sizeDif = result[SIZE_DIF]

            toResize.setFontPoint(newFontPoint)

        i -= 1

    if not newFontPoint:
        toResizeCopy, toCompareCopy = TextLine.copy(toResize), TextLine.copy(toCompare)

        sizeDif = TextLine.resize(toResize, toCompare, resizeMode)
        newFontPoint = toResize.getFontPoint()

        RESIZE_RESULTS += [
            (
                toResizeCopy,
                toCompareCopy,
                resizeMode,
                newFontPoint,
                sizeDif,
            )
        ]

    return sizeDif


def extendTabAlignment(
    toExtend: TextLine, toCompare: TextLine, toCompareWhitespace=0.0, tabGroup=1
) -> float:
    """Extend TextLine (with tabs) to match an anchor TextLine. Result are cached.

    Note:
        The cache returns identical results for similar parameters.

        When toExtend changes, a new cache entry is made.

        If toCompare (anchor) changes width, cache will return invalid result.

    See also:
        `TextLine.extendTabAlignmentWidth()`

    Args:
        toExtend (TextLine): TextLine to extend.
        toCompare (TextLine): TextLine to compare.
        toCompareWhitespace (float, optional): To compare's, unaccounted for extra width. Defaults to 0.0.
        tabGroup (int, optional): Tab group to extend (1-n). Defaults to 1.

    Returns:
        float: Total width of toExtend's new tabs.
    """
    global EXTEND_RESULTS
    tabOffset = cast(float, None)

    TO_EXTEND, TO_COMPARE, WHITESPACE, TAB_GROUP, RESULT = 0, 1, 2, 3, 4
    NEW_TEXT, WIDTH_DIF = 0, 1
    i = len(EXTEND_RESULTS) - 1  # Read cache from newest.
    while not tabOffset and i > -1:
        result = EXTEND_RESULTS[i]
        if (
            toExtend == result[TO_EXTEND]
            and toCompare.compareStyle(result[TO_COMPARE])
            and toCompareWhitespace == result[WHITESPACE]
            and tabGroup == result[TAB_GROUP]
        ):
            tabOffset = result[RESULT][WIDTH_DIF]
            toExtend.setText(result[RESULT][NEW_TEXT])

            x, y = toExtend.getPos()
            toExtend.setPos((x - tabOffset, y))

        i -= 1

    if not tabOffset:
        toDrawCopy, toCompareCopy = TextLine.copy(toExtend), TextLine.copy(toCompare)

        tabOffset = TextLine.extendTabAlignment(
            toExtend, toCompare, toCompareWhitespace, tabGroup
        )

        EXTEND_RESULTS += [
            (
                toDrawCopy,
                toCompareCopy,
                toCompareWhitespace,
                tabGroup,
                (toExtend.getText(), tabOffset),
            )
        ]

    return tabOffset


def default(linesToDraw: list[TextLine]) -> None:
    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = cast(float, None)
    centerPoint = cast(float, None)
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i])

        if i == bottomLine:
            excessRKern = TextLine.getExcessKerning(
                linesToDraw[i], TextMetric.RIGHT_KERNING
            )

            x = imgW + offX - txtW + excessRKern - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        else:
            x = imgW + offX - (txtW / 2) - centerPoint
            y = baseline + offY - txtH

        linesToDraw[i].setPos((x, y))
        baseline = y + offL - LEADING

    if (
        linesToDraw[TIME].getSize()[TextLine.WIDTH]
        > linesToDraw[DATE].getSize()[TextLine.WIDTH]
    ):
        widthDif = extendTabAlignment(linesToDraw[DATE], linesToDraw[TIME]) / 2
        for line in linesToDraw[:-1]:
            line.setPos(
                (line.getPos()[TextLine.X] - widthDif, line.getPos()[TextLine.Y])
            )


def layoutOne(linesToDraw: list[TextLine]) -> None:
    def default_x_pos():
        return imgW + offX - (txtW / 2) - centerPoint

    def default_y_pos():
        return baseline + offY - txtH

    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = cast(float, None)
    centerPoint = cast(float, None)
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i])

        if DATE == i:
            # Align date to bottom right corner with a margin
            excessRKern = TextLine.getExcessKerning(
                linesToDraw[i], TextMetric.RIGHT_KERNING
            )

            x = imgW + offX - txtW + excessRKern - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        elif TIME == i:
            year = linesToDraw[DATE].getText().rsplit(TextLine.SPACE, 1)[-1]
            yearTL = TextLine.copyStyle(linesToDraw[DATE], year)
            yearWidth = yearTL.getSize()[TextLine.WIDTH]
            yearLeftKern, _ = TextLine.getKerningWidth(yearTL)

            excessRKern = TextLine.getExcessKerning(
                linesToDraw[i], TextMetric.RIGHT_KERNING
            )

            # Align the time TextLine to the left of the year
            x = imgW + offX - txtW + excessRKern + yearLeftKern - yearWidth - MARGIN
            y = default_y_pos()
        elif AMPM == i:
            _, ampmRKern = TextLine.getKerningWidth(linesToDraw[AMPM])
            colon = TextLine.copyStyle(linesToDraw[TIME], ":")
            colonOffY = colon.getOffset()[TextLine.OFFSET_Y]

            # Align ampm denoter using the colon in time
            # Remove right kerning to force text flush to margin
            x = imgW + offX - txtW + ampmRKern - MARGIN
            y = baseline + colonOffY + offY - txtH
        else:
            x = default_x_pos()
            y = default_y_pos()

        linesToDraw[i].setPos((x, y))

        nextLine = i - 1  # reverse order of index
        if AMPM == nextLine:  # set baseline to ASCENT
            baseline = y - offY
        else:  # set baseline to maintain LEADING
            baseline = y + offL - LEADING

    # Now make the date the largest TextLine,
    # by moving the day of week abr to the far left.
    extendTabAlignment(
        linesToDraw[DATE],
        linesToDraw[TIME],
        (  # TIME's trailing whitespace (not included in width)
            linesToDraw[TIME].getImgSize()[TextLine.WIDTH]
            - linesToDraw[TIME].getSize()[TextLine.WIDTH]
            - linesToDraw[TIME].getPos()[TextLine.X]
            - MARGIN
        ),
    )


def layoutTwo(linesToDraw: list[TextLine]) -> None:
    global AMPM, TIME, DATE

    def default_x_pos() -> float:
        return imgW + offX - (txtW / 2) - centerPoint

    def default_y_pos() -> float:
        return baseline + offY - txtH

    # combine TIME and AMPM to one line
    combineTimeAmPm(linesToDraw, colonSpacing=True)

    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = cast(float, None)
    centerPoint = cast(float, None)
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i])

        if DATE == i:
            excessRKern = TextLine.getExcessKerning(
                linesToDraw[i], TextMetric.RIGHT_KERNING
            )

            x = imgW + offX - txtW + excessRKern - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        else:
            x = default_x_pos()
            y = default_y_pos()

        linesToDraw[i].setPos((x, y))
        baseline = y + offL - LEADING

    # Extend date TextLine
    if (
        linesToDraw[DATE].getSize()[TextLine.WIDTH]
        < linesToDraw[TIME].getSize()[TextLine.WIDTH]
    ):
        widthDif = extendTabAlignment(linesToDraw[DATE], linesToDraw[TIME])
        linesToDraw[TIME].setPos(
            (
                linesToDraw[TIME].getPos()[TextLine.X] - (widthDif / 2),
                linesToDraw[TIME].getPos()[TextLine.Y],
            )
        )

    # Grow time TextLine to match date width
    (widthDif, heightDif), (offXDif, offYDif) = resizeTextLine(
        linesToDraw[TIME], linesToDraw[DATE], Resize.GROW
    )

    # Reset time position
    linesToDraw[TIME].setPos(
        (
            linesToDraw[TIME].getPos()[TextLine.X] + offXDif - (widthDif / 2),
            linesToDraw[TIME].getPos()[TextLine.Y] + offYDif - heightDif,
        )
    )


def layoutThree(linesToDraw: list[TextLine]) -> None:
    def default_x_pos():
        return imgW + offX - (txtW / 2) - centerPoint

    def default_y_pos():
        return baseline + offY - txtH

    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = cast(float, None)
    centerPoint = cast(float, None)
    indent = 0
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i])

        if DATE == i:
            # Align date to bottom right corner with a margin
            excessRKern = TextLine.getExcessKerning(
                linesToDraw[i], TextMetric.RIGHT_KERNING
            )

            x = imgW + offX - txtW + excessRKern - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        elif TIME == i:
            indent = (  # add kerning offset using line composition
                TextLine.copyStyle(linesToDraw[DATE], "0").getSize()[TextLine.WIDTH] / 2
            )
            excessRKern = TextLine.getExcessKerning(
                linesToDraw[i], TextMetric.RIGHT_KERNING
            )

            x = imgW + offX - txtW + excessRKern - indent - MARGIN
            y = default_y_pos()
        elif AMPM == i:
            _, ampmRKern = TextLine.getKerningWidth(linesToDraw[AMPM])
            indent *= 0.9

            x = imgW + offX - txtW + ampmRKern - indent - MARGIN
            y = default_y_pos()
        else:
            x = default_x_pos()
            y = default_y_pos()

        linesToDraw[i].setPos((x, y))
        baseline = y + offL - LEADING

    # Extend DATE TextLine by extending day of week tab alignment.
    extendTabAlignment(
        linesToDraw[DATE],
        linesToDraw[TIME],
        (  # TIME's trailing whitespace (not included in width)
            linesToDraw[TIME].getImgSize()[TextLine.WIDTH]
            - linesToDraw[TIME].getSize()[TextLine.WIDTH]
            - linesToDraw[TIME].getPos()[TextLine.X]
            - MARGIN
        ),
    )


def setPosition(linesToDraw: list[TextLine]) -> None:
    """Set TextLines position.

    See also:
        `Overlay`

    Args:
        linesToDraw (list[TextLine]): TextLines to draw.

    Raises:
        NotImplementedError: Layout does not exist.
    """
    match LAYOUT:
        case Overlay.DEFAULT:
            default(linesToDraw)
        case Overlay.LAYOUT_1:
            layoutOne(linesToDraw)
        case Overlay.LAYOUT_2:
            layoutTwo(linesToDraw)
        case Overlay.LAYOUT_3:
            layoutThree(linesToDraw)
        case _:  # default
            raise NotImplementedError("Layout does not exist.")


def getTopAdjustedMargin(highestLine: TextLine) -> float:
    """Get top adjusted Margin.

    Args:
        highestLine (TextLine): Highest TextLine in the overlay.

    Returns:
        float: Top adjusted margin, in px.
    """
    return MARGIN - getLeadingOffset(highestLine)


def getLeftAdjustedMargin(leftmostLine: TextLine) -> float:
    """Get left adjusted Margin.

    Args:
        highestLine (TextLine): Leftmost TextLine in the overlay.

    Returns:
        float: Left adjusted margin, in px.
    """
    return MARGIN - TextLine.getExcessKerning(leftmostLine, TextMetric.LEFT_KERNING)


def setBorder(linesToDraw: list[TextLine], DEBUG_MODE: bool = False) -> None:
    """Set TextLines border and border color.

    \nNotes:
        -TextLines border is relative to the longest (leftmost) TextLine.\n
        -HighestLine has lowest y value; Use OffL to maintain accurate border size.\n
        -LowestLine has highest y value; Use min descender to maintain accurate border size.

    \nArgs:
        linesToDraw (list[TextLine]): TextLines to draw.\n
        DEBUG_MODE (bool, optional): Calculate border using TextLines, instead of image. Defaults to False.
    """
    highestLine = search(linesToDraw, FindLine.HIGHEST)
    lowestLine = search(linesToDraw, FindLine.LOWEST)
    anchorLine = search(linesToDraw, FindLine.LEFTMOST)
    rightmostLine = search(linesToDraw, FindLine.RIGHTMOST)

    highestLineTop = highestLine.getPos()[TextLine.Y]
    topAdjustedMargin = getTopAdjustedMargin(highestLine)

    anchorLineTop = anchorLine.getPos()[TextLine.Y]
    anchorLineBottom = (
        anchorLineTop - anchorLine.getOffset()[TextLine.OFFSET_Y]
    ) + anchorLine.getSize()[TextLine.HEIGHT]
    anchorLineEnd = (
        anchorLine.getPos()[TextLine.X] + anchorLine.getSize()[TextLine.WIDTH]
    )
    leftAdjustedMargin = getLeftAdjustedMargin(anchorLine)

    topBorder = (anchorLineTop - highestLineTop) + topAdjustedMargin
    leftBorder = leftAdjustedMargin

    if DEBUG_MODE:  # relative to text
        rightmostLineEnd = (
            rightmostLine.getPos()[TextLine.X] + rightmostLine.getSize()[TextLine.WIDTH]
        )
        rightAdjustedMargin = MARGIN - TextLine.getExcessKerning(
            rightmostLine, TextMetric.RIGHT_KERNING
        )

        lowestLineTop = lowestLine.getPos()[TextLine.Y]
        lowestLineBottom = (
            lowestLineTop - lowestLine.getOffset()[TextLine.OFFSET_Y]
        ) + lowestLine.getSize()[TextLine.HEIGHT]
        bottomAdjustedMargin = MARGIN - TextLine.getDescenderMinHeight(anchorLine)

        rightBorder = (rightmostLineEnd - anchorLineEnd) + rightAdjustedMargin
        bottomBorder = (lowestLineBottom - anchorLineBottom) + bottomAdjustedMargin
    else:  # relative to image
        imgW, imgH = anchorLine.getImgSize()

        rightBorder = imgW - anchorLineEnd
        bottomBorder = imgH - anchorLineBottom

    anchorLine.setBorderSize((topBorder, rightBorder, bottomBorder, leftBorder))
    anchorLine.setBorderColor(BORDER_COLOR)


def shiftPosition(linesToDraw: list[TextLine]) -> None:
    """Shift position of TextLines to their final location.\n

    \nNotes:
        TextLines are drawn in the `BOTTOM_RIGHT`, then shifted.

    \nSee also:
        `Location`

    \nArgs:
        linesToDraw (list[TextLine]): TextLines to draw.

    \nRaises:
        NotImplementedError: Location unsupported.
    """
    highestLine = search(linesToDraw, FindLine.HIGHEST)
    leftmostLine = search(linesToDraw, FindLine.LEFTMOST)

    topHighestLine = highestLine.getPos()[TextLine.Y]
    topAdjustedMargin = getTopAdjustedMargin(highestLine)
    offTop = topHighestLine - topAdjustedMargin

    startLongestLine = leftmostLine.getPos()[TextLine.X]
    leftAdjustedMargin = getLeftAdjustedMargin(leftmostLine)
    offLeft = startLongestLine - leftAdjustedMargin

    if LOCATION == Location.TOP_RIGHT:
        # subtract top offset
        for line in linesToDraw:
            (posX, posY) = line.getPos()
            line.setPos((posX, posY - offTop))
    elif LOCATION == Location.BOTTOM_LEFT:
        # subtract left offset
        for line in linesToDraw:
            (posX, posY) = line.getPos()
            line.setPos((posX - offLeft, posY))
    elif LOCATION == Location.TOP_LEFT:
        # subtract top and left offset
        for line in linesToDraw:
            (posX, posY) = line.getPos()
            line.setPos((posX - offLeft, posY - offTop))
    else:
        raise NotImplementedError("Location unsupported.")


def getStrsMaxWidth(lineStyle: TextLine, strList: list[str]) -> int:
    """Get the max width of the strings in a list.

    Args:
        lineStyle (TextLine): TextLine style to copy.
        strList (list[str]): Strings to measure.

    Returns:
        int: Max width, in px.
    """
    styleCopy = TextLine.copyStyle(lineStyle, "")
    maxWidth = 0

    for str in strList:
        width = styleCopy.setText(str).getSize()[TextLine.WIDTH]
        maxWidth = max(maxWidth, width)

    return maxWidth


def minAlignmentTabs(lineStyle: TextLine, strList: list[str]) -> int:
    """Get the minimum number of tabs needed to equally align all strings in the list.

    Args:
        lineStyle (TextLine): TextLine style for strings.
        strList (list[str]): List of strings to align.

    Returns:
        int: Minimum number of tabs.
    """
    global MIN_TABS
    minTabs = cast(int, None)

    LINE_STYLE, STR_LIST, RESULT = 0, 1, 2
    i = len(MIN_TABS) - 1  # Read cache from newest.
    while not minTabs and i > -1:
        result = MIN_TABS[i]
        if lineStyle.compareStyle(result[LINE_STYLE]) and strList is result[STR_LIST]:
            minTabs = result[RESULT]
        i -= 1

    if not minTabs:
        lineStyleCopy = TextLine.copy(lineStyle)

        tabWidth = TextLine.getTabWidth(lineStyle.getFont())
        maxWidth = getStrsMaxWidth(lineStyle, strList)
        minTabs = math.ceil(maxWidth / tabWidth)

        MIN_TABS += [(lineStyleCopy, strList, minTabs)]

    return minTabs


def combineDayDate(linesToDraw: list[TextLine]) -> TextLine:
    """Get combined day and date TextLine.\n
    Note:
        Output TextLine matches date style.

    Args:
        dayOfWeek (TextLine): TextLine for day of week.
        date (TextLine): TextLine for date.

    Returns:
        TextLine: Combined TextLine.
    """
    global DAY, DATE, TAB_COUNT
    date = linesToDraw[DATE]
    dayOfWeek = linesToDraw[DAY]

    # Align month
    date.setText((TextLine.SPACE * 2).join(date.getText().split(TextLine.SPACE, 1)))
    monthMinTabs = minAlignmentTabs(date, MONTHS)
    TextLine.addTabAlignment(date, loc=2, length=monthMinTabs, reverse=not STATIC_DATE)

    # Align day of week and combine with date
    date.setText(dayOfWeek.getText() + " " + date.getText())
    dayMinTabs = minAlignmentTabs(date, DAYS_OF_WEEK)
    
    dayMinTabs += TAB_COUNT  # DELETE ME *************************************************************************
    TAB_COUNT += 1
    
    TextLine.addTabAlignment(date, loc=1, length=dayMinTabs)

    del linesToDraw[DAY]
    DAY = cast(int, None)  # Day is now null
    DATE -= 1

    return date


def combineTimeAmPm(
    linesToDraw: list[TextLine], colonSpacing: bool = False
) -> TextLine:
    """Get combined time and ampm TextLine.\n

    Note:
        Output TextLine matches time style.

    Args:
        linesToDraw (list[TextLine]): TextLines to draw.
        colonSpace (bool, optional): Add decorative spacing to time. Defaults to False.

    Returns:
        TextLine: Combined TextLine.
    """
    global AMPM, TIME, DATE
    ampm = linesToDraw[AMPM]
    time = linesToDraw[TIME]

    time.setText(
        (time.getText().replace(":", " : ") if colonSpacing else time.getText())
        + " "
        + ampm.getText()
    )

    del linesToDraw[AMPM]
    AMPM = cast(int, None)  # AMPM is now null

    TIME -= 1
    DATE -= 1

    return time


def regexSplit(
    linesToDraw: list[TextLine],
    index: int,
    pattern: str,
    splitIndex: int = 0,
    reverseKeywords: list[str] = [],
) -> None:
    """Split TextLine using a regex pattern.

    NOTE:
        Reverse split moves only split start, whereas split moves only split end.\n
        Put your reverse splitter keyword(s) at the end of str and they will be processed at the start of str.

    Args:
        linesToDraw (list[TextLine]): TextLines to draw.
        index (int): TextLine index.
        pattern (str): Regex pattern.
        splitIndex (int, optional): Remove/keep part of the regex result. Defaults to 0.
        reverseKeywords (list[str], optional): If keyword found in result, reverse split. Defaults to [].
    """
    START, END = 0, 1
    text = linesToDraw[index].getText()

    for result in re.findall(pattern, text):
        split = text.split(result, 1)
        start = linesToDraw[index]  # line to split
        end = TextLine.copyStyle(linesToDraw[index], result[splitIndex:] + split[END])

        x, y = start.getPos()
        originalOffY = start.getOffset()[TextLine.OFFSET_Y]
        offY = end.getOffset()[TextLine.OFFSET_Y] - originalOffY
        offX = start.setText(split[START] + result[:splitIndex]).getSize()[
            TextLine.WIDTH
        ]

        start.setText(split[START])  # line split here

        # set positions
        end.setPos((x + offX, y + offY))

        offY = start.getOffset()[TextLine.OFFSET_Y] - originalOffY
        if any(reverseKeyword in result for reverseKeyword in reverseKeywords):
            # move regex result width to left of START, instead of the right
            offX -= start.getSize()[TextLine.WIDTH]
            start.setPos((x + offX, y + offY))
        else:
            start.setPos((x, y + offY))

        # save lines
        if start.getText() == TextLine.EMPTY and end.getText() != TextLine.EMPTY:
            linesToDraw[index] = end  # replace start with end
        elif end.getText() != TextLine.EMPTY:
            linesToDraw.append(end)  # keep start and append end to list
            index = -1  # next loop will split the 'end' TextLine

        text = linesToDraw[index].getText()  # reset text


def removeLeadingZero(linesToDraw: list[TextLine]) -> None:
    """Remove leading zero from TextLines.

    Args:
        linesToDraw (list[TextLine]): TextLines to draw.
    """
    TIME_PATTERN = r"0[0-9]:[0-5][0-9]"
    DATE_PATTERN = r"(?<!:)\b0\d{1}\b"

    if LAYOUT == Overlay.LAYOUT_2:
        TIME_PATTERN = r"0[0-9] : [0-5][0-9]"
        DATE_PATTERN = r"(?<!: )\b0\d{1}\b"

    pattern = "{}|{}".format(TIME_PATTERN, DATE_PATTERN)
    splitIndex = 1  # split and remove zero ([0 | 1 ... n] - char indexes).

    for i in range(0, len(linesToDraw)):
        regexSplit(linesToDraw, i, pattern, splitIndex)


def tabAdapter(linesToDraw: list[TextLine]) -> None:
    """FFmpeg TextLine tab adapter.

    Note:
        Tabs are calculated locally, not natively by FFmpeg.

    Args:
        linesToDraw (list[TextLine]): TextLines to draw.
    """
    TAB_PATTERN = "{}+".format(TextLine.TAB)
    REVERSE_TAB_PATTERN = "{}+".format(TextLine.REVERSE_TAB)

    pattern = "{}|{}".format(TAB_PATTERN, REVERSE_TAB_PATTERN)
    splitIndex = sys.maxsize  # remove splitter

    for i in range(0, len(linesToDraw)):
        regexSplit(linesToDraw, i, pattern, splitIndex, [TextLine.REVERSE_TAB])


def incrementProgress() -> None:
    """Increment program progress."""
    global IMAGES_RENDERED, LOCK

    LOCK.acquire()
    IMAGES_RENDERED += 1
    LOCK.release()


def drawOverlay(inputDir: str, filename: str, outputDir: str) -> threading.Thread:
    """Draw overlay onto an image.

    Args:
        inputDir (str): Input directory for Image.
        filename (str): Image filename.
        outputDir (str): Output directory for result.

    Returns:
        threading.Thread: Render thread for TextLine overlay.
    """
    global AMPM, TIME, DAY, DATE
    imgPath = os.path.join(inputDir, filename)
    imgName = os.path.splitext(filename)[0]  # Remove file extension
    img = Image.open(imgPath)

    splitDate = ParseDate.getFormattedDate(ParseDate.parseDate(imgName)).split("\n")
    AMPM, TIME, DAY, DATE = 0, 1, 2, 3
    linesToDraw = [
        TextLine(splitDate[AMPM], SMALL_FONT, SMALL_FONT_POINT, SMALL_FONT_COLOR, img),
        TextLine(splitDate[TIME], LARGE_FONT, LARGE_FONT_POINT, LARGE_FONT_COLOR, img),
        TextLine(splitDate[DAY], SMALL_FONT, SMALL_FONT_POINT, SMALL_FONT_COLOR, img),
        TextLine(splitDate[DATE], SMALL_FONT, SMALL_FONT_POINT, SMALL_FONT_COLOR, img),
    ]

    combineDayDate(linesToDraw)

    setPosition(linesToDraw)

    # WARNING: TLs are split below and can no longer be modified using their indexes.
    # ===============================================================================

    tabAdapter(linesToDraw)

    if not LEADING_ZERO:
        removeLeadingZero(linesToDraw)

    if BORDER:
        setBorder(linesToDraw)

    if LOCATION != Location.BOTTOM_RIGHT:
        shiftPosition(linesToDraw)

    overlayRenderer = threading.Thread(
        target=TextLine.drawTextLines,
        args=(
            imgName,
            imgPath,
            linesToDraw,
            BORDER,
            outputDir,
            RENDER_ENGINE,
            incrementProgress,
        ),
    )
    overlayRenderer.start()

    return overlayRenderer


def countImages(directory: str) -> int:
    """Count images inside a directory.

    Args:
        directory (str): Directory.

    Returns:
        int: Image count.
    """
    imageFiles = (
        glob.glob(os.path.join(directory, "*.jpg"))
        + glob.glob(os.path.join(directory, "*.jpeg"))
        + glob.glob(os.path.join(directory, "*.png"))
    )

    return len(imageFiles)


def printProgressThreaded(imagesToRender: int) -> None:
    """Thread to track render progress.

    See also:
        `printProgress()`

    Args:
        imagesToRender (int): Total images to render.
    """
    global IMAGES_RENDERED
    COMPLETE = 100

    done = False
    while not done:
        progress = (IMAGES_RENDERED / imagesToRender) * 100

        printProgress(progress)

        if progress == COMPLETE or STOP_EVENT.is_set():
            done = True


def printProgress(progress: float) -> None:
    """Print progress.

    Args:
        progress (float): Progress (0% to 100%).
    """
    PROGRESS_PER_BAR = 5
    i = int(progress / PROGRESS_PER_BAR)
    bar = " " + "[" + "=" * i + " " * (20 - i) + "]"
    sign = " %"
    progStr = f"{progress:.1f}"[:-2] + " COMPLETE"
    print(f"{bar}{sign}{progStr: >{12}}", end="\r", flush=True)


def applyOverlayToDir(inputDir: str) -> None:
    """Apply overlay to directory of images.

    \nNotes:
        Result is nondestructive, new images are saved to an output directory.

    \nArgs:
        inputDir (str): Input path.
    """
    if not os.path.isdir(inputDir):
        raise FileNotFoundError(f"The directory '{inputDir}' does not exist.")

    outputDir = os.path.join(inputDir, "output")
    os.makedirs(outputDir, exist_ok=True)

    threadedProgress = threading.Thread(
        target=printProgressThreaded, args=(countImages(inputDir),)
    )
    print("Please wait, drawing overlay onto images...")
    threadedProgress.start()

    overlayRenderers: list[threading.Thread] = []

    for filename in os.listdir(inputDir):
        if (
            filename.endswith(".jpg")
            or filename.endswith(".jpeg")
            or filename.endswith(".png")
        ):
            try:
                overlayRenderers.append(drawOverlay(inputDir, filename, outputDir))
            except Exception as e:
                STOP_EVENT.set()  # Stop progress thread
                time.sleep(0.01)
                print("Error drawing overlay: " + str(e))

    for overlayRenderer in overlayRenderers:
        overlayRenderer.join()

    if overlayRenderers:
        threadedProgress.join()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python " + SCRIPT_NAME + " <directory_path>")
        sys.exit(1)

    inputDir = sys.argv[1]
    start_time = time.time()  # DELETE ME
    applyOverlayToDir(inputDir)
    print()  # don't overwrite progress bar
    print(
        "Process finished --- %s seconds ---" % (time.time() - start_time)
    )  # DELETE ME
