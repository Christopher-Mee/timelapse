"""
Christopher Mee
2024-07-01
Line of text, positioned in relation to an image.
"""

from __future__ import annotations  # For forward references in type hints

import math
import os
import re
import subprocess  # FFmpeg
import sys
from enum import Enum
from functools import lru_cache
from typing import cast, Callable

from PIL import Image, ImageFile, ImageFont, ImageDraw
from PIL._typing import Coords


class RenderEngine(Enum):
    """Render engine used to draw TextLines."""

    PILLOW = 0
    FFMPEG = 1


class Resize(Enum):
    """Resize mode.

    See also:
        `TextLine.resize()`
    """

    GROW = 0
    SHRINK = 1


class FindMetric(Enum):
    """Search mode.

    See also:
        `searchMetric()`
    """

    LARGEST = 0
    SMALLEST = 1


class TextMetric(Enum):
    """Text metric.

    See also:
        `searchMetric()`
    """

    LEFT_KERNING = 0
    RIGHT_KERNING = 1
    X_OFFSET = 2
    Y_OFFSET = 3


class TextLine:
    """A text line to be drawn on to an image."""

    # POSITION INDEXES
    X, Y = 0, 1

    # SIZE INDEXES
    WIDTH, HEIGHT = 0, 1

    # OFFSET INDEXES
    OFFSET_X, OFFSET_Y = 0, 1

    # KERNING INDEXES
    KERNING_LEFT, KERNING_RIGHT = 0, 1

    # BBOX INDEXES
    X1, Y1, X2, Y2 = 0, 1, 2, 3

    # BORDER WIDTH INDEXES
    BORDER_TOP, BORDER_RIGHT, BORDER_BOTTOM, BORDER_LEFT = 0, 1, 2, 3

    # ASCII SUBSETS
    NUMBER = list(range(48, (57 + 1)))  # 0-9
    UPPER = list(range(65, (90 + 1)))  # A-Z
    LOWER = list(range((65 + 32), (90 + 32 + 1)))  # a-z
    COMMA = [44]  # ,
    COLON = [58]  # :

    # TAB HELPERS
    TAB_SIZE = 2  # in SPACES
    TAB = "\t"
    REVERSE_TAB = "\r"
    DELIMITERS = [TAB, REVERSE_TAB]  # Add all delimiters here
    EMPTY = ""
    SPACE = " "

    # STATIC HELPERS
    @staticmethod
    def getBbox(textLine: TextLine) -> tuple[int, int, int, int]:
        """Get bounding box.\n
        The bounding box is used to get text size without any excess whitespace.

        Args:
            textLine (TextLine): TextLine.

        Returns:
            tuple[int, int, int, int]: Text bounding box (`X1`, `Y1`, `X2`, `Y2`).
        """
        bbox = textLine.getFont().getmask(textLine.getText(True)).getbbox()

        tabsWidth = 0  # px
        if TextLine.TAB in textLine.getText():
            tabsWidth = TextLine.getTabsWidth(textLine.getFont(), textLine.getText())

        return (
            bbox[TextLine.X1],
            bbox[TextLine.Y1],
            bbox[TextLine.X2] + tabsWidth,
            bbox[TextLine.Y2],
        )

    @staticmethod
    def getBboxWidth(bbox: tuple[int, int, int, int]) -> int:
        """Get bounding box width.

        Args:
            bbox (tuple[int, int, int, int]): Text bounding box (`X1`, `Y1`, `X2`, `Y2`).

        Returns:
            int: Width, in px.
        """
        return bbox[TextLine.X2] - bbox[TextLine.X1]

    @staticmethod
    def getBboxHeight(bbox: tuple[int, int, int, int]) -> int:
        """Get bounding box height.

        Args:
            bbox (tuple[int, int, int, int]): Text bounding box (`X1`, `Y1`, `X2`, `Y2`).

        Returns:
            int: Height, in px.
        """
        return bbox[TextLine.Y2] - bbox[TextLine.Y1]

    @staticmethod
    def getBboxSize(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
        """Get bounding box size.

        Args:
            bbox (tuple[int, int, int, int]): Text bounding box (`X1`, `Y1`, `X2`, `Y2`).

        Returns:
            tuple[int, int]: (`WIDTH`, `HEIGHT`), in px.
        """
        return TextLine.getBboxWidth(bbox), TextLine.getBboxHeight(bbox)

    @staticmethod
    def getDescenderMinHeight(textLine: TextLine) -> int:
        """Get descender minimum height.\n
        'Minimum' refers to the utilized height below the baseline, without any \n
        excess whitespace.

        Args:
            textLine (TextLine): TextLine.

        Returns:
            int: Minimum height, in px.
        """
        bboxH = TextLine.getBboxHeight(TextLine.getBbox(textLine))
        txtH = textLine.getSize()[TextLine.HEIGHT]
        offY = textLine.getOffset()[TextLine.OFFSET_Y]

        return bboxH - (txtH - offY)

    @staticmethod
    def getKerningWidth(textLine: TextLine) -> tuple[int, int]:
        """Get Kerning width.

        Args:
            textLine (TextLine): TextLine.

        Returns:
            tuple[int, int]: (`KERNING_LEFT`, `KERNING_RIGHT`), in px.
        """
        bbox = TextLine.getBbox(textLine)

        kerningLeft = bbox[TextLine.X1]
        kerningRight = textLine.getSize()[TextLine.WIDTH] - bbox[TextLine.X2]

        return kerningLeft, kerningRight

    @staticmethod
    @lru_cache(maxsize=None)
    def getTabWidth(font: ImageFont.FreeTypeFont) -> int:
        """Get single tab width.

        See also:
            `TextLine.TAB_SIZE`

        Args:
            font (ImageFont.FreeTypeFont): Font style (font and font point).

        Returns:
            int: Width, in px.
        """
        (spaceWidth, _), (_, _) = font.font.getsize(TextLine.SPACE)
        return TextLine.TAB_SIZE * spaceWidth

    @staticmethod
    @lru_cache(maxsize=None)
    def getTabsWidth(font: ImageFont.FreeTypeFont, text: str) -> int:
        """Get total tabs widths.\n
        NOTE: Tabs are NOT natively supported by `PIL`.

        Args:
            font (ImageFont.FreeTypeFont): Font style (font and font point).
            text (str): Text (including delimiters).

        Returns:
            int: Total width of all tabs, in px.
        """
        TAB_WIDTH = TextLine.getTabWidth(font)
        PATTERN = "{}|{}".format(TextLine.TAB, TextLine.REVERSE_TAB)
        tabsWidthTotal = 0  # in px

        split = re.split(PATTERN, text)
        for text in split[:-1]:
            (textW, _), (_, _) = font.font.getsize(text)
            tabOverlap = textW % TAB_WIDTH
            tabsWidthTotal += TAB_WIDTH - tabOverlap

        return tabsWidthTotal

    @staticmethod
    @lru_cache(maxsize=None)
    def getAsciiRange(textLine: TextLine) -> list[int]:
        """Get TextLine composition.

        \nTextLine composition (includes one or more of the following ranges):
        `NUMBER` `UPPER` `LOWER` `COMMA` `COLON`

        \nThe result should be used to predict which characters a TextLine may
        \ncontain in the future, assuming the TextLine subject remains consistent.



        \nArgs:
        \n    textLine (TextLine): TextLine.

        \nReturns:
        \n    list[int]: TextLine composition.
        """
        text = textLine.getText(True)
        asciiCodes = [ord(char) for char in text]

        lineComposition = []
        for code in asciiCodes:
            if code not in lineComposition:
                if code in TextLine.UPPER:
                    lineComposition += TextLine.UPPER
                elif code in TextLine.LOWER:
                    lineComposition += TextLine.LOWER
                elif code in TextLine.NUMBER:
                    lineComposition += TextLine.NUMBER
                elif code in TextLine.COMMA:
                    lineComposition += TextLine.COMMA
                elif code in TextLine.COLON:
                    lineComposition += TextLine.COLON

        return lineComposition

    @staticmethod
    @lru_cache(maxsize=None)
    def getExcessKerning(textLine: TextLine, kerningSide: TextMetric) -> int:
        """Get excess kerning width.

        See also:
            `TextMetric.RIGHT_KERNING`, `TextMetric.LEFT_KERNING`

        Args:
            textLine (TextLine): TextLine to measure.
            kerningSide (TextMetric): Left or right side kerning.

        Raises:
            ValueError: TextMetric not supported.

        Returns:
            int: Excess kerning whitespace width.
        """
        FIRST_CHAR, LAST_CHAR = 0, -1
        excess = 0

        match kerningSide:

            case TextMetric.RIGHT_KERNING:
                end = TextLine.copyStyle(textLine, textLine.getText(True)[LAST_CHAR])
                excess = TextLine.searchMetric(
                    end, FindMetric.SMALLEST, TextMetric.RIGHT_KERNING
                )

            case TextMetric.LEFT_KERNING:
                start = TextLine.copyStyle(textLine, textLine.getText(True)[FIRST_CHAR])
                excess = TextLine.searchMetric(
                    start, FindMetric.SMALLEST, TextMetric.LEFT_KERNING
                )

            case _:  # default
                raise ValueError(
                    "TextMetric not supported. Use RIGHT_KERNING or LEFT_KERNING."
                )

        return excess

    @staticmethod
    def searchMetric(
        textLine: TextLine, mode: FindMetric, attribute: TextMetric
    ) -> int:
        """Search TextLine composition metrics.

        Note:
            Used to create a text alignment anchor point and/or remove empty whitespace.

        Args:
            textLine (TextLine): TextLine.
            mode (FindMetric): Search mode.
            attribute (TextMetric): TextLine composition metric.

        Returns:
            int: Result.
        """
        if mode == FindMetric.SMALLEST:
            compareOperation = -1
            result = sys.maxsize
        elif mode == FindMetric.LARGEST:
            compareOperation = 1
            result = -sys.maxsize - 1
        else:
            return NotImplemented

        tempLine = TextLine.copyStyle(textLine, "")
        for char in TextLine.getAsciiRange(textLine):
            if attribute == TextMetric.X_OFFSET:
                toCompare = tempLine.setText(chr(char)).getOffset()[TextLine.OFFSET_X]
            elif attribute == TextMetric.Y_OFFSET:
                toCompare = tempLine.setText(chr(char)).getOffset()[TextLine.OFFSET_Y]
            elif attribute == TextMetric.LEFT_KERNING:
                toCompare = TextLine.getKerningWidth(tempLine.setText(chr(char)))[
                    TextLine.KERNING_LEFT
                ]
            elif attribute == TextMetric.RIGHT_KERNING:
                toCompare = TextLine.getKerningWidth(tempLine.setText(chr(char)))[
                    TextLine.KERNING_RIGHT
                ]
            else:
                return NotImplemented

            if (toCompare * compareOperation) > (result * compareOperation):
                result = toCompare

        return result

    @staticmethod
    def resize(
        toResize: TextLine, toCompare: TextLine, mode: Resize
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Resize TextLine, relative to another.

        Args:
            toResize (TextLine): TextLine to resize.
            toCompare (TextLine): TextLine to compare.
            mode (Resize): Resize mode (`GROW`, `SHRINK`).

        Raises:
            ValueError: Invalid resize mode.

        Returns:
            tuple[tuple[float, float], tuple[float, float]]: Difference between original and new size, \n
                (widthDif, HeightDif), (xOffDif, yOffDif).
        """
        (originalWidth, originalHeight), (originalOffX, originalOffY) = (
            toResize.getSize(),
            toResize.getOffset(),
        )

        if mode == Resize.SHRINK:
            while (
                toResize.getSize()[TextLine.WIDTH] > toCompare.getSize()[TextLine.WIDTH]
            ):
                newPoint = toResize.getFontPoint() - 1
                toResize.setFontPoint(newPoint)
        elif mode == Resize.GROW:
            while (
                toResize.getSize()[TextLine.WIDTH] < toCompare.getSize()[TextLine.WIDTH]
            ):
                newPoint = toResize.getFontPoint() + 1
                toResize.setFontPoint(newPoint)
        else:
            return NotImplemented

        (newWidth, newHeight), (newOffX, newOffY) = (
            toResize.getSize(),
            toResize.getOffset(),
        )

        return (
            (newWidth - originalWidth, newHeight - originalHeight),
            (newOffX - originalOffX, newOffY - originalOffY),
        )

    @staticmethod
    def addTabAlignment(
        textLine: TextLine, loc: int, length: int, reverse: bool = False
    ) -> None:
        """Add tab alignment to TextLine.

        Note:
            Location is based on pre-existing spaces in the TextLine.

        See also:
            `TextLine.TAB_SIZE`

        Args:
            textLine (TextLine): TextLine.
            loc (int): Location (0-n) to insert alignment.
            length (int): Length of alignment in tabs.
        """
        NOT_FOUND = -1  # rfind() flag
        TAB_SIZE = TextLine.getTabWidth(textLine.getFont())
        TAB_ALIGNMENT_SIZE = TAB_SIZE * length
        TAB_TYPE = TextLine.TAB if not reverse else TextLine.REVERSE_TAB

        split = textLine.getText().split(TextLine.SPACE, loc)
        start = " ".join(split[0:loc])
        end = split[loc]

        lastTabIndex = start.rfind(TextLine.TAB)
        lastRTabIndex = start.rfind(TextLine.REVERSE_TAB)
        lastTabStopIndex = max(lastTabIndex, lastRTabIndex)

        if lastTabStopIndex == NOT_FOUND:
            textLine.setText(start)
        else:
            if lastTabIndex == lastTabStopIndex:
                tabLength = len(TextLine.TAB)
            else:
                tabLength = len(TextLine.REVERSE_TAB)

            # truncate to only text after the last tab stop
            textLine.setText(start[lastTabStopIndex + tabLength :])

        startWidth = textLine.getSize()[TextLine.WIDTH]
        tabsToAdd = math.ceil((TAB_ALIGNMENT_SIZE - startWidth) / TAB_SIZE) * TAB_TYPE
        textLine.setText(start + tabsToAdd + end)

    @staticmethod
    def extendTabAlignment(
        toDraw: TextLine,
        toCompare: TextLine,
        toCompareWhitespace: float = 0,
        tabGroup: int = 1,
    ) -> float:
        """Extend tab alignment width, relative to another.

        Args:
            toDraw (TextLine): TextLine to draw.
            toCompare (TextLine): TextLine to compare.
            toCompareWhitespace (float, optional): To compare's, unaccounted for extra width. Defaults to 0.
            tabGroup (int, optional): Tab group to extend (1-n). Defaults to 1.

        Returns:
            float: To draw's newly added tabs width.
        """
        TAB_SIZE = TextLine.getTabWidth(toDraw.getFont())
        splitter = TextLine.TAB
        split = toDraw.getText().split(splitter)
        tabsToAdd = math.ceil(
            (
                (toCompare.getSize()[TextLine.WIDTH] + toCompareWhitespace)
                - toDraw.getSize()[TextLine.WIDTH]
            )
            / TAB_SIZE
        )
        tabsToAddWidth = tabsToAdd * TAB_SIZE

        if tabsToAdd > 0:
            # find the index where tabs should be added
            tabGroupIndex = -1
            for i in range(0, tabGroup):
                tabGroupIndex += 1
                while (tabGroupIndex + 1 < len(split)) and (
                    split[tabGroupIndex + 1] == TextLine.EMPTY
                ):
                    tabGroupIndex += 1

            split[tabGroupIndex] += tabsToAdd * TextLine.TAB
            newText = splitter.join(split)
            toDraw.setText(newText).setPos(
                (
                    toDraw.getPos()[TextLine.X] - tabsToAddWidth,
                    toDraw.getPos()[TextLine.Y],
                )
            )
        else:
            tabsToAddWidth = 0

        return tabsToAddWidth

    @staticmethod
    def delimitFFmpegPath(filepath: str) -> str:
        """Delimit file path, in order to work within an FFmpeg command.

        Args:
            filepath (str): File path.

        Returns:
            str: Delimited file path.
        """
        return filepath.replace(":", "\\\\:")

    @staticmethod
    def delimitFFmpegText(text: str) -> str:
        """Delimit text, in order to work within an FFmpeg command.

        Args:
            text (str): Text to delimit.

        Returns:
            str: Delimited text.
        """
        DELIMITER = "\\"

        # fix command execution error
        text = text.replace(":", DELIMITER + ":")

        # allow preceding whitespace to be drawn
        precedingSpace = " " == text[0]
        if precedingSpace:
            text = DELIMITER + text

        return text

    @staticmethod
    def importBorder(
        textLine: TextLine, engine: RenderEngine
    ) -> list[str] | tuple[Coords, str]:
        """Import border into render engine.

        Args:
            textLine (TextLine): TextLine to import.
            renderEngine (Engine): Engine used to draw.

        Returns:
            list[str]: Exported border.
        """
        borderSize = textLine.getBorderSize()
        borderColor = textLine.getBorderColor()

        if not borderSize:
            raise ValueError("Border size not set.")

        if not borderColor:
            raise ValueError("Border color not set.")

        x, y = textLine.getPos()
        width, _ = textLine.getSize()
        height = textLine.getTrueHeight()

        topLeft = (
            x - borderSize[TextLine.BORDER_LEFT],
            y - borderSize[TextLine.BORDER_TOP],
        )

        bottomRight = (
            x + width + borderSize[TextLine.BORDER_RIGHT],
            y + height + borderSize[TextLine.BORDER_BOTTOM],
        )

        match engine:

            case RenderEngine.FFMPEG:
                exportedBorder = []

                bW, bH = (
                    bottomRight[TextLine.X] - topLeft[TextLine.X],
                    bottomRight[TextLine.Y] - topLeft[TextLine.Y],
                )

                exportedBorder.extend(
                    [
                        topLeft[TextLine.X],
                        topLeft[TextLine.Y],
                        bW,
                        bH,
                        borderColor,
                    ]
                )
                return exportedBorder

            case RenderEngine.PILLOW:
                bottomRight = bottomRight[TextLine.X] - 1, bottomRight[TextLine.Y] - 1
                return [topLeft, bottomRight], borderColor

            case _:  # default
                raise NotImplementedError("Render Engine does not exist.")

    @staticmethod
    def importTextLineToFFmpeg(textLine: TextLine) -> list[str]:
        """Import TextLine in to FFmpeg.

        Args:
            textLine (TextLine): TextLine to import.

        Returns:
            list[str]: Exported TextLine.
        """
        exportedTextLine = []

        exportedTextLine.extend(
            [
                TextLine.delimitFFmpegPath(textLine.getFontFile()),
                textLine.getFontPoint(),
                textLine.getColor(),
                TextLine.delimitFFmpegText(textLine.getText()),
            ]
        )

        exportedTextLine.extend(
            [
                textLine.getPos()[TextLine.X],
                textLine.getPos()[TextLine.Y],
            ]
        )

        return exportedTextLine

    @staticmethod
    def getFFmpegCMD(
        imgName: str,
        imgPath: str,
        textLines: list[TextLine],
        hasBorder: bool,
        outputDir: str,
    ) -> str:
        """Get FFmpeg command, which draws the TextLines on to the base image.

        Args:
            imgName (str): Image filename (excluding file extension).
            imgPath (str): Image file path.
            textLines (list[TextLine]): TextLines to draw.
            hasBorder (bool): If True, draw border.
            outputDir (str): Output file path.

        Returns:
            str: FFmpeg command.
        """
        START_CMD = '"'
        DRAW_TEXT = "drawtext=fontfile={}:fontsize={}:fontcolor={}:text='{}':x={}:y={}"
        DRAW_BORDER = "format=rgb24, drawbox=x={}:y={}:w={}:h={}:color={}:t=fill"
        APPEND_CMD = ","
        EMD_CMD = '"'

        textLineCMDs = []
        cmdBuilder = START_CMD

        if hasBorder:  # NOTE: Border must be drawn first.
            COMPLETE = False
            i = 0
            while not COMPLETE and i < len(textLines):
                if textLines[i].getBorderSize():
                    cmdBuilder += DRAW_BORDER + APPEND_CMD
                    cmdBuilder = cmdBuilder.format(
                        *TextLine.importBorder(textLines[i], RenderEngine.FFMPEG)
                    )
                    textLineCMDs.append(cmdBuilder)
                    cmdBuilder = ""  # reset
                    COMPLETE = True
                i += 1

        for i in range(0, len(textLines)):
            cmdBuilder += DRAW_TEXT

            if textLines[-1] is textLines[i]:
                cmdBuilder += EMD_CMD
            else:
                cmdBuilder += APPEND_CMD

            cmdBuilder = cmdBuilder.format(
                *TextLine.importTextLineToFFmpeg(textLines[i])
            )
            textLineCMDs.append(cmdBuilder)
            cmdBuilder = ""  # reset

        return " ".join(
            [
                "ffmpeg",
                "-i",
                '"{}"'.format(imgPath),
                "-vf",
            ]
            + textLineCMDs
            + [
                "-y",
                "-frames:v 1",
                "-update true",
                '"{}"'.format(os.path.join(outputDir, f"{imgName}.png")),
            ],
        )

    @staticmethod
    def drawTextLines(
        imgName: str,
        imgPath: str,
        linesToDraw: list[TextLine],
        hasBorder: bool,
        outputDir: str,
        renderEngine: RenderEngine,
        incrementProgress: Callable | None,
    ) -> None:
        """Draw TextLines from a list.

        Args:
            imgName (str): Image filename (excluding file extension).
            imgPath (str): Image file path.
            linesToDraw (list[TextLine]): TextLines to draw.
            hasBorder (bool): If True, draw border.
            outputDir (str): Output file path.
            renderEngine (Engine): Engine used to draw.
            incrementProgress (Callable | None): Function to increment progress. Defaults to None.

        Raises:
            NotImplementedError: Render engine does not exist.
        """
        match renderEngine:

            case RenderEngine.FFMPEG:
                subprocess.Popen(
                    TextLine.getFFmpegCMD(
                        imgName, imgPath, linesToDraw, hasBorder, outputDir
                    ),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                ).wait()

            case RenderEngine.PILLOW:
                TRANSPARENT = "#FFFFFF00"
                RGBA = "RGBA"
                IMG_EXT = ".png"
                FORMAT = "PNG"

                img = linesToDraw[0].getImg().convert(RGBA)

                # draw border
                if hasBorder:
                    XY, BORDER_COLOR = 0, 1
                    border = Image.new(RGBA, img.size, TRANSPARENT)
                    draw = ImageDraw.Draw(border)

                    exportedBorder = cast(
                        tuple[Coords, str],
                        TextLine.importBorder(
                            next(line for line in linesToDraw if line.getBorderSize()),
                            RenderEngine.PILLOW,
                        ),
                    )

                    draw.rectangle(exportedBorder[XY], exportedBorder[BORDER_COLOR])
                    img = Image.alpha_composite(img, border)

                # draw textLines
                textLines = Image.new(RGBA, img.size, TRANSPARENT)
                draw = ImageDraw.Draw(textLines)

                for line in linesToDraw:
                    draw.text(
                        line.getPos(),
                        line.getText(),
                        line.getColor(),
                        line.getFont(),
                        anchor="lt",  # left, top
                    )
                img = Image.alpha_composite(img, textLines)

                # save result
                os.makedirs(outputDir, exist_ok=True)
                img.save(os.path.join(outputDir, imgName + IMG_EXT), FORMAT)

            case _:  # default
                raise NotImplementedError("Render engine does not exist.")

        if incrementProgress:
            incrementProgress()

    # CONSTRUCTOR
    def __init__(
        self,
        text: str,
        fontFile: str,
        fontPoint: int,
        color: str,
        img: ImageFile.ImageFile,
    ) -> None:
        """Initialize new TextLine.

        Args:
            text (str): Contents of the text line.
            fontFile (str): Font file path.
            fontPoint (int): Font size.
            color (str): Text hex color code.
            img (ImageFile.ImageFile): Base image, where text will be drawn.
        """
        # passed
        self.text = text
        self.fontPoint = fontPoint
        self.fontFile = fontFile
        self.color = color
        self.img = img

        # dependent
        self.font = ImageFont.truetype(fontFile, fontPoint)
        self.size = cast(tuple[int, int], None)
        self.trueHeight = cast(int, None)
        self.offset = cast(tuple[int, int], None)
        self.setSize()

        # uninitialized
        self.position: tuple[float, float] = cast(tuple[float, float], None)
        self.borderSize: tuple[float, float, float, float] = cast(
            tuple[float, float, float, float], None
        )
        self.borderColor: str = cast(str, None)

    # COMPARATORS
    def __eq__(self, other: object) -> bool:
        """Compare TextLines.

        Args:
            other (object): Object being compared against.

        Returns:
            bool: Is equal?
        """
        if not isinstance(other, type(self)):
            return NotImplemented

        return (
            self.text == other.text
            and self.fontFile == other.fontFile
            and self.fontPoint == other.fontPoint
            and self.color == other.color
            # and self.img.filename == other.img.filename
            and self.position == other.position
            and self.borderSize == other.borderSize
            and self.borderColor == other.borderColor
        )

    def compareStyle(self, other: object) -> bool:
        """Compare TextLines, based solely on style.

        Args:
            other (object): Object being compared against.

        Returns:
            bool: Is style equal?
        """
        if not isinstance(other, type(self)):
            return NotImplemented

        return (
            self.fontFile == other.fontFile
            and self.fontPoint == other.fontPoint
            and self.color == other.color
        )

    # HASH
    def __hash__(self) -> int:
        """Hash TextLine.

        Returns:
            int: TextLine hash.
        """
        return hash(
            (
                self.text,
                self.fontFile,
                self.fontPoint,
                self.color,
                # self.img.filename,
                self.position,
                self.borderSize,
                self.borderColor,
            )
        )

    # FACTORY METHODS
    @classmethod
    def copy(cls, textLine: TextLine) -> TextLine:
        """Copy TextLine.

        Args:
            textLine (TextLine): TextLine to copy.

        Returns:
            TextLine: TextLine copy.
        """
        copy = cls(
            textLine.getText(),
            textLine.getFontFile(),
            textLine.getFontPoint(),
            textLine.getColor(),
            textLine.getImg(),
        )

        if textLine.getPos():
            copy.setPos(textLine.getPos())

        if textLine.getBorderSize():
            copy.setBorderSize(textLine.getBorderSize())

        if textLine.getBorderColor():
            copy.setBorderColor(textLine.getBorderColor())

        return copy

    @classmethod
    def copyStyle(cls, textLine: TextLine, text: str) -> TextLine:
        """Create a TextLine copy, with the same style as the original TextLine.

        Args:
            textLine (TextLine): Original TextLine.
            text (str): New text.

        Returns:
            TextLine: TextLine copy.
        """
        return cls(
            text,
            textLine.getFontFile(),
            textLine.getFontPoint(),
            textLine.getColor(),
            textLine.getImg(),
        )

    # GETTERS
    def getText(self, REMOVE_DELIMITERS: bool = False) -> str:
        """Get TextLine text.

        Args:
            REMOVE_DELIMITERS (bool, optional): Defaults to False.

        Returns:
            str: Text.
        """
        if REMOVE_DELIMITERS:
            cleanText = self.text
            for delimiter in TextLine.DELIMITERS:
                cleanText = cleanText.replace(delimiter, TextLine.EMPTY)
            return cleanText
        else:
            return self.text

    def getFontFile(self) -> str:
        """Get TextLine font file.

        Returns:
            str: Font file path.
        """
        return self.fontFile

    def getFontPoint(self) -> int:
        """Get TextLine font point.

        Returns:
            int: Font size.
        """
        return self.fontPoint

    def getFont(self) -> ImageFont.FreeTypeFont:
        """Get TextLine font.

        Returns:
            ImageFont.FreeTypeFont: Font style (font and font point).
        """
        return self.font

    def getPos(self) -> tuple[float, float]:
        """Get TextLine position.

        See also:
            `getOffset()`

        Raises:
            TypeError: If None, position is null.

        Returns:
            tuple[float, float]: (`X`, `Y`) position, where text is drawn on to the base image. Default is None (null).
        """
        return self.position

    def getImg(self) -> ImageFile.ImageFile:
        """Get TextLine base image.

        Returns:
            ImageFile.ImageFile: Base image, text is drawn on to.
        """
        return self.img

    def getImgSize(self) -> tuple[int, int]:
        """Get TextLine base image size.

        Returns:
            tuple[int, int]: (`WIDTH`, `HEIGHT`), in px.
        """
        return self.img.size

    def getSize(self) -> tuple[int, int]:
        """Get the TextLine size.\n

        Note:
            Size includes kerning.

        See also:
            `TextLine.setSize()`

            `TextLine.getKerningSize()`

        Returns:
            tuple[int, int]: (`WIDTH`, `HEIGHT`), in px.
        """
        return self.size

    def getTrueHeight(self) -> int:
        """Get the TextLine true height, NOT the ascent.

        WARNING:
            This includes the descender.

        Returns:
            int: True height, in px.
        """
        return self.trueHeight

    def getOffset(self) -> tuple[int, int]:
        """Get the TextLine offset.\n
        Indentation from the TextLine position.

        See also:
            `getPos()`

        Returns:
            tuple[int, int]: (`OFFSET_X`, `OFFSET_Y`), in px.
        """
        return self.offset

    def getBorderSize(self) -> tuple[float, float, float, float] | None:
        """Get TextLine border size.\n
        \nBorder widths:
        (`BORDER_TOP`, `BORDER_RIGHT`, `BORDER_BOTTOM`, `BORDER_LEFT`)

        \nReturns:
        \n    tuple[float, float, float, float] | None: Border widths, in px. Defaults to None (null).
        """
        return self.borderSize

    def getBorderColor(self) -> str | None:
        """Get the TextLine border color.

        Returns:
            str | None: Hex color code. Defaults to None (null).
        """
        return self.borderColor

    def getColor(self) -> str:
        """Get the TextLine text color.

        Returns:
            str: Hex color code.
        """
        return self.color

    # SETTERS
    def setPos(self, position: tuple[float, float]) -> TextLine:
        """Set TextLine position, in relation to the base image.

        Args:
            position (tuple[float, float]): (`X`, `Y`) anchor point, where text is drawn on to the base image.

        Raises:
            ValueError: position invalid

        Returns:
            TextLine: Self.
        """
        if (
            0 > position[self.X] > self.img.width
            or 0 > position[self.Y] > self.img.height
        ):
            raise ValueError("Position invalid!")

        self.position = position

        return self

    def setSize(self) -> TextLine:
        """Set TextLine size (`WIDTH`, `HEIGHT`) and offset (`OFFSET_X`, `OFFSET_Y`), in px.\n
        When a TextLine attribute is modified, `setSize()` must be rerun.

        Returns:
            TextLine: Self.
        """
        # independent of the text contents
        ascent, _ = self.font.getmetrics()  # ignore descent

        # dependent on the text contents
        (textWidth, textHeight), (offset_x, offset_y) = self.font.font.getsize(
            self.getText(True)
        )
        textWidth += TextLine.getTabsWidth(self.font, self.getText())

        self.trueHeight = textHeight
        self.size = (textWidth, ascent)
        self.offset = (offset_x, offset_y)

        return self

    def setText(self, text: str) -> TextLine:
        """Set TextLine text.

        Args:
            text (str): New text.

        Returns:
            TextLine: Self.
        """
        self.text = text
        self.setSize()

        return self

    def setBorderSize(
        self, borderSize: tuple[float, float, float, float] | None
    ) -> TextLine:
        """Set TextLine border size.\n

        Note:
            Border widths:
            (`BORDER_TOP`, `BORDER_RIGHT`, `BORDER_BOTTOM`, `BORDER_LEFT`)

        Args:
            borderSize (tuple[float, float, float, float] | None): Border widths, in px. None, means null.

        Returns:
            TextLine: Self.
        """
        if borderSize:
            self.borderSize = borderSize

        return self

    def setBorderColor(self, borderColor: str | None) -> TextLine:
        """Set TextLine border color.

        Args:
            borderColor (str | None): Hex color code. None, means null.

        Returns:
            TextLine: Self.
        """
        if borderColor:
            self.borderColor = borderColor

        return self

    def setFontPoint(self, fontPoint: int) -> TextLine:
        """Set TextLine font point.

        Args:
            fontPoint (int): Size of text.

        Returns:
            TextLine: Self.
        """
        self.fontPoint = fontPoint
        self.font = ImageFont.truetype(self.fontFile, fontPoint)
        self.setSize()

        return self
