"""
Christopher Mee
2024-07-01
Draw a date & time overlay onto images using FFmpeg.

== KNOWN ISSUES ===============================================================
Currently the date is not drawn consistantly. The day abrv has an alignment 
issue. This issue is caused by the lack of tab support in PIL and FFmpeg.

== WARNING ====================================================================
Not all fonts are supported. If your selected font is not being displayed 
properly, try a different font. (Some fonts have invalid attributes, that 
result in text which cannot be drawn consistantly.)

== Starter Guide for Drawing Text =============================================
    Width and height are helpful but dont tell the full story. You need to 
indent by the x and y offsets to draw text accurately. Then you can go further 
and use the bounding box (bbox) to remove preceding and trailing whitespace 
called kerning.

    To draw the next line, you need to subtract the prev offset Y from the 
prev lines Y pos to get a new baseline. The baseline will be a consistant 
anchor point, but leaves a large whitespace gap above the prev text line. This 
will cause your leading to be inaccurate and look bad. My approach to solving 
this problem, is to brute-force parse the font file to determine and minimize 
the Y offset. And in doing so, creating a new leading offset, which minimizes 
whitespace, while maintaing a consistant anchor point.

== Diagram ====================================================================
    *
    *
    *
    OFF_Y
    ASCENDER
    TEXT
    BASELINE ________________
    DESCENDER
    LEADING
    OFF_Y
    ASCENDER
    TEXT
    BASELINE ________________
    DESCENDER
    MARGIN

== Resources ==================================================================
https://ffmpeg.org/ffmpeg-filters.html#drawtext
https://stackoverflow.com/a/68664685
"""

import time
import os
import re
import sys
import subprocess
import glob
from enum import Enum

from PIL import Image

import ParseDate
from TextLine import TextLine


# ENUM
class Overlay(Enum):
    DEFAULT = 0
    LAYOUT_1 = 1
    LAYOUT_2 = 2


class Location(Enum):
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3


# FINAL
SCRIPT_NAME = os.path.basename(__file__)
USERNAME = os.getlogin()

# == FONT =====================================================================
HELVETICA = "C:/Users/" + USERNAME + "/Desktop/New Font/Helvetica___.ttf"
HELVETICA_BOLD = "C:/Users/" + USERNAME + "/Desktop/New Font/HelveticaBd.ttf"

# == SETTINGS =================================================================
# date, ampm str
SMALL_FONT = HELVETICA_BOLD
SMALL_FONT_POINT = 36
SMALL_FONT_COLOR = "#FFFFFF"

# time str
LARGE_FONT = HELVETICA
LARGE_FONT_POINT = 72
LARGE_FONT_COLOR = "#FFFFFF"

# overlay
LAYOUT = Overlay.LAYOUT_1
LOCATION = Location.BOTTOM_RIGHT
MARGIN = 10  # in px
LEADING = MARGIN  # in px

# border
BORDER = False
BORDER_COLOR = "#00000040"

# modifier
LEADING_ZERO = True
# =============================================================================

# CACHE
RESIZE_RESULTS = []
LEADING_OFFSETS = []
ASCII_RANGES = []


def getAsciiRange(textLine, id=None):
    """Get the composition of a TextLine object.\n
    This information is used to minimize the y offset.

    Args:
        textLine (TextLine): TextLine object
        id (int, optional): unique identifier. Defaults to None.

    Returns:
        List[int, ...]: All possible ascii codes used by the TextLine.
    """
    global ASCII_RANGES
    asciiRange = None

    ID, RESULT = 0, 1
    i = 0
    while not asciiRange and i < len(ASCII_RANGES):
        result = ASCII_RANGES[i]
        if id == result[ID]:
            asciiRange = result[RESULT]
        i += 1

    if not asciiRange:
        asciiRange = TextLine.getAsciiRange(textLine)
        ASCII_RANGES += [(id, asciiRange)]

    return asciiRange


def getLeadingOffset(textLine, asciiRange, offY):
    """Get the leading offset and save result.\n
    The smallest offset y is the highest offset, making it a good anchor point.

    Args:
        textLine (TextLine): A TextLine Object
        asciiRange (List[int, ...]): List of ascii codes

    Returns:
        int: smallest offset y
    """
    global LEADING_OFFSETS
    fontFile = textLine.getFontFile()
    fontPoint = textLine.getFontPoint()
    smallestOffY = None

    FONT_FILE, FONT_POINT, ASCII_RANGE, RESULT = 0, 1, 2, 3
    i = 0
    while not smallestOffY and i < len(LEADING_OFFSETS):
        result = LEADING_OFFSETS[i]
        if (
            fontFile == result[FONT_FILE]
            and fontPoint == result[FONT_POINT]
            and asciiRange == result[ASCII_RANGE]
        ):
            smallestOffY = result[RESULT]

        i += 1

    if not smallestOffY:
        smallestOffY = TextLine.getSmallestOffY(textLine, asciiRange)
        LEADING_OFFSETS += [(fontFile, fontPoint, asciiRange, smallestOffY)]

    return smallestOffY - offY


def resizeTextLine(toResize, toCompare, resizeMode):
    """Resize TextLine and save result.

    Args:
        toResize (TextLine): TextLine object
        toCompare (TextLine): TextLine object
        resizeMode (int): Resize mode constant
    """
    global RESIZE_RESULTS
    fontFile = toResize.getFontFile()
    fontPoint = toResize.getFontPoint()
    newFontPoint = None

    FONT_FILE, FONT_POINT, RESIZE_MODE, RESULT = 0, 1, 2, 3
    i = 0
    while not newFontPoint and i < len(RESIZE_RESULTS):
        result = RESIZE_RESULTS[i]
        if (
            fontFile == result[FONT_FILE]
            and fontPoint == result[FONT_POINT]
            and resizeMode == result[RESIZE_MODE]
        ):
            newFontPoint = result[RESULT]
            toResize.setFontPoint(newFontPoint)

        i += 1

    if not newFontPoint:
        TextLine.resize(toResize, toCompare, resizeMode)
        newFontPoint = toResize.getFontPoint()
        RESIZE_RESULTS += [(fontFile, fontPoint, resizeMode, newFontPoint)]


def defaultOverlay(linesToDraw):
    """Date and time overlay, all centered, bottom right, three lines.

    Args:
        linesToDraw (list[TextLine]): TextLine Objects
    """
    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = None
    centerPoint = None
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i], getAsciiRange(linesToDraw[i], i), offY)

        if i == bottomLine:
            x = imgW + offX - txtW - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        else:
            x = imgW + offX - (txtW / 2) - centerPoint
            y = baseline + offY - txtH

        linesToDraw[i].setPos((x, y))
        baseline = y + offL - LEADING


def layoutOneOverlay(linesToDraw):
    """Date and time overlay, bottom left corner, three lines.

    Args:
        linesToDraw (list[TextLine]): TextLine Objects
    """
    AMPM, TIME, DATE = 0, 1, 2

    def default_x_pos():
        return imgW + offX - (txtW / 2) - centerPoint

    def default_y_pos():
        return baseline + offY - txtH

    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = None
    centerPoint = None
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i], getAsciiRange(linesToDraw[i], i), offY)

        if DATE == i:
            # Align date to bottom right corner with a margin
            x = imgW + offX - txtW - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        elif TIME == i:
            year = linesToDraw[DATE].getText().split(" ")[-1]
            yearTL = TextLine.copyStyle(linesToDraw[DATE], year)
            yearWidth = yearTL.getSize()[TextLine.WIDTH]
            yearleftKern, _ = TextLine.getKerningSize(yearTL)

            # Align the time TextLine to the left of the year
            x = imgW + offX - txtW + yearleftKern - yearWidth - MARGIN
            y = default_y_pos()
        elif AMPM == i:
            _, ampmRKern = TextLine.getKerningSize(linesToDraw[AMPM])
            colon = TextLine.copyStyle(linesToDraw[TIME], ":")
            colonOffY = colon.getOffset()[TextLine.Y_OFFSET]

            # Align ampm denoter using the colon in time
            # Remove right kerning to force text flush to margin
            x = imgW + offX - txtW + ampmRKern - MARGIN
            y = baseline + colonOffY + offY - txtH
        else:
            x = default_x_pos()
            y = default_y_pos()

        linesToDraw[i].setPos((x, y))

        nextLine = i - 1
        if AMPM == nextLine:  # set baseline to offY
            baseline = y - offY
        else:  # set basline to LEADING
            baseline = y + offL - LEADING


def layoutTwoOverlay(linesToDraw):
    """Date and time overlay, bottom left corner, two lines.

    Args:
        linesToDraw (list[TextLine]): TextLine Objects
    """
    AMPM, TIME, DATE = 0, 1, 2

    def default_x_pos():
        return imgW + offX - (txtW / 2) - centerPoint

    def default_y_pos():
        return baseline + offY - txtH

    bottomLine, topLine = (len(linesToDraw) - 1), (0 - 1)
    baseline = None
    centerPoint = None
    for i in range(bottomLine, topLine, -1):
        imgW, imgH = linesToDraw[i].getImgSize()
        txtW, txtH = linesToDraw[i].getSize()
        offX, offY = linesToDraw[i].getOffset()
        offL = getLeadingOffset(linesToDraw[i], getAsciiRange(linesToDraw[i], i), offY)

        if DATE == i:
            x = imgW + offX - txtW - MARGIN
            y = imgH - MARGIN + offY - txtH

            centerPoint = offX + (txtW / 2) + MARGIN
        elif TIME == i:
            # combine TIME and AMPM to one line
            timeWSpace = linesToDraw[TIME].getText().replace(":", " : ")
            combinedTL = timeWSpace + " " + linesToDraw[AMPM].getText()
            linesToDraw[TIME].setText(combinedTL)

            resizeTextLine(linesToDraw[TIME], linesToDraw[DATE], TextLine.SHRINK)
            txtW, txtH = linesToDraw[TIME].getSize()
            offX, offY = linesToDraw[TIME].getOffset()

            x = default_x_pos()
            y = default_y_pos()
        elif AMPM == i:
            del linesToDraw[AMPM]
        else:
            x = default_x_pos()
            y = default_y_pos()

        linesToDraw[i].setPos((x, y))
        baseline = y + offL - LEADING


def setPosition(linesToDraw):
    """Align and set the position of TextLines in preparation of being drawn onto an image.\n
    All TextLines are centered in relation to the first line.

    Args:
        linesToDraw (tuple[TextLine, ...]): A tuple of TextLine objects that need to be positioned, in relation to the same img.
    """
    match LAYOUT:
        case Overlay.DEFAULT:
            defaultOverlay(linesToDraw)
        case Overlay.LAYOUT_1:
            layoutOneOverlay(linesToDraw)
        case Overlay.LAYOUT_2:
            layoutTwoOverlay(linesToDraw)
        case _:
            raise NotImplementedError  # Default error


def setBorder(textLines, maintainMargin=True):
    """Set the border for all textLines.\n
    NOTE: The border is relative to the largest line.

    Args:
        textLines (List[TextLine, ...]): TextLine objects
        maintainMargin (bool, optional): Ignore excess whitespace. Defaults to True.
    """
    heighestLine = textLines[0]
    lowestLine = textLines[-1]

    # find longest line
    longestLine = textLines[0]
    for i in range(1, len(textLines)):
        if (
            textLines[i].getSize()[TextLine.WIDTH]
            > longestLine.getSize()[TextLine.WIDTH]
        ):
            longestLine = textLines[i]

    # Reference points needed to set border widths
    topHeighestLine = heighestLine.getPos()[TextLine.Y]
    topLongestLine = longestLine.getPos()[TextLine.Y]
    bottomLongestLine = (
        topLongestLine
        - longestLine.getOffset()[TextLine.Y_OFFSET]
        + longestLine.getSize()[TextLine.HEIGHT]
    )
    topLowestLine = lowestLine.getPos()[TextLine.Y]
    bottomLowestLine = (
        topLowestLine
        - lowestLine.getOffset()[TextLine.Y_OFFSET]
        + lowestLine.getSize()[TextLine.HEIGHT]
    )

    # compare longestLine to heighestLine
    # heighestLine has lowest y value
    # **Need to use leading offset to get consistant top border width**
    borderTop = topLongestLine - topHeighestLine + MARGIN
    if maintainMargin:  # Allow extra whitespace to maintain consistant margin
        heighestLineOffY = heighestLine.getOffset()[TextLine.Y_OFFSET]
        offL = getLeadingOffset(
            heighestLine, getAsciiRange(heighestLine, -1), heighestLineOffY
        )
        borderTop -= offL

    # compare longestLine to lowestLine
    # lowestLine has heighest y value
    # **The bottom border starts at the bottom descender**
    borderBottom = bottomLowestLine - bottomLongestLine + MARGIN
    if maintainMargin:  # Allow the descender into the margin
        borderBottom -= TextLine.getDescenderMinHeight(longestLine)

    borderRight = borderLeft = MARGIN

    longestLine.setBorderSize((borderTop, borderRight, borderBottom, borderLeft))
    longestLine.setBorderColor(BORDER_COLOR)


def shiftPosition(textLines):
    """Shift textLines to match their intended location.\n
    Currently text is drawn in the bottom right corner, then shifted.\n
    NOTE: location (left, right) does not match justification.

    Args:
        textLines (List[TextLine, ...]): List of TextLine objects.
    """
    heighestLine = textLines[0]
    longestLine = textLines[0]
    for i in range(1, len(textLines)):
        if (
            textLines[i].getSize()[TextLine.WIDTH]
            > longestLine.getSize()[TextLine.WIDTH]
        ):
            longestLine = textLines[i]

    topHeighestLine = heighestLine.getPos()[TextLine.Y]
    offTop = topHeighestLine - MARGIN

    longestLineXPos = longestLine.getPos()[TextLine.X]
    offLeft = longestLineXPos - MARGIN

    if LOCATION == Location.TOP_RIGHT:
        # subtract top offset
        for line in textLines:
            (posX, posY) = line.getPos()
            line.setPos((posX, posY - offTop))
    elif LOCATION == Location.BOTTOM_LEFT:
        # subtract left offset
        for line in textLines:
            (posX, posY) = line.getPos()
            line.setPos((posX - offLeft, posY))
    elif LOCATION == Location.TOP_LEFT:
        # subtract top and left offset
        for line in textLines:
            (posX, posY) = line.getPos()
            line.setPos((posX - offLeft, posY - offTop))
    else:
        # location unknown
        NotImplementedError


def drawOverlay(inputDir, filename, outputDir):
    """Apply a date & time text overlay onto an image using FFmpeg.

    Args:
        inputDir (str): directory of the image
        filename (str): filename of the image
        outputDir (str): output directory, if different orginal image isn't overwritten
    """
    imgName = os.path.splitext(filename)[0]  # Remove file extension
    imgPath = os.path.join(inputDir, filename)
    img = Image.open(imgPath)

    AM_PM, TIME, DATE = 0, 1, 2
    splitDate = ParseDate.getFormattedDate(ParseDate.parseDate(imgName)).split("\n")
    textLines = [
        TextLine(splitDate[AM_PM], SMALL_FONT, SMALL_FONT_POINT, SMALL_FONT_COLOR, img),
        TextLine(splitDate[TIME], LARGE_FONT, LARGE_FONT_POINT, LARGE_FONT_COLOR, img),
        TextLine(splitDate[DATE], SMALL_FONT, SMALL_FONT_POINT, SMALL_FONT_COLOR, img),
    ]

    # modify textlines here
    # ensure all attributes are accurate, when calculating position.
    if not LEADING_ZERO:
        REPLACEMENT_WHITESPACE = "  "
        time = textLines[TIME].getText()
        date = textLines[DATE].getText()

        strippedTime = time.lstrip("0")
        if strippedTime != time:
            time = REPLACEMENT_WHITESPACE + strippedTime
            textLines[TIME].setText(time)

        date = re.sub(r"\b0(\d)", REPLACEMENT_WHITESPACE + r"\1", date)
        textLines[DATE].setText(date)

    # get textline positions here
    setPosition(textLines)

    # if needed, reorder indexes here
    if Overlay.LAYOUT_2 == LAYOUT:
        TIME, DATE = 0, 1

    # modify other attributes here
    if BORDER:
        setBorder(textLines)

    # run this last
    shiftPosition(textLines)

    FFmpegCMD = TextLine.getFFmpegCMD(imgName, imgPath, textLines, BORDER, outputDir)
    subprocess.Popen(
        FFmpegCMD, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )  # .wait() # beware adding this slows down the program considerably


def countImages(directory):
    """Get the number of images located in a specified directory.

    Args:
        directory (str): directory to parse

    Returns:
        int: image count
    """
    imageFiles = (
        glob.glob(os.path.join(directory, "*.jpg"))
        + glob.glob(os.path.join(directory, "*.jpeg"))
        + glob.glob(os.path.join(directory, "*.png"))
    )

    return len(imageFiles)


def printProgress(progress):
    """Print progress of slow program.

    Args:
        progress (int): 0 to 100 percent
    """
    i = int(progress / 5)  # 5% progress per bar drawn
    bar = " " + "[" + "=" * i + " " * (20 - i) + "]"
    sign = " %"
    progress = f"{progress:.1f}"[:-2] + " COMPLETE"
    print(f"{bar}{sign}{progress: >{12}}", end="\r", flush=True)


def applyOverlayToDir(inputDir):
    """Apply overlay (nondestuctive) to every image in the input directory.\n
    All overlayed images are placed in a new output directory.

    Args:
        inputDir (str): input directory
    """
    imagesToProcess = countImages(inputDir)
    imagesCompleted = 0

    outputDir = os.path.join(inputDir, "output")
    os.makedirs(outputDir, exist_ok=True)

    print("Please wait, drawing overlay onto images...")

    for filename in os.listdir(inputDir):
        if (
            filename.endswith(".jpg")
            or filename.endswith(".jpeg")
            or filename.endswith(".png")
        ):
            drawOverlay(inputDir, filename, outputDir)

            imagesCompleted += 1
            printProgress((imagesCompleted / imagesToProcess) * 100)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python " + SCRIPT_NAME + " <directory_path>")
        sys.exit(1)

    inputDir = sys.argv[1]
    start_time = time.time()
    applyOverlayToDir(inputDir)
    print("Process finished --- %s seconds ---" % (time.time() - start_time))
