"""
Christopher Mee
2024-07-01
Object representing a line of text, positioned in relation to an image.
"""

import sys
import os
from functools import lru_cache

from PIL import ImageFont


class TextLine:
    """A text line to be drawn on an image."""

    # indexes

    # axis
    X = 0
    Y = 1

    # size
    WIDTH = 0
    HEIGHT = 1

    # offset
    X_OFFSET = 0
    Y_OFFSET = 1

    # bbox
    X1 = 0
    Y1 = 1
    X2 = 2
    Y2 = 3

    # ascii subset
    NUMBER = list(range(48, (57 + 1)))  # 0-9
    UPPER = list(range(65, (90 + 1)))  # A-Z
    LOWER = list(range((65 + 32), (90 + 32 + 1)))  # a-z
    COMMA = [44]  # ,
    COLON = [58]  # :

    # resize
    GROW = 1
    SHRINK = -1

    # static helpers
    @staticmethod
    def getBbox(textLine):
        """Get text bounding box for the TextLine object.\n
        The bbox is useful for finding the size of text without the proceding and trailing kerning.

        Args:
            textLine (TextLine): A TextLine object

        Returns:
            tuple[int, int, int, int]: text bounding box
        """
        return textLine.getFont().getmask(textLine.getText()).getbbox()

    @staticmethod
    def getBboxWidth(bbox):
        """Get the width of the text bounding box

        Args:
            bbox (tuple[int, int, int, int]): text bounding box

        Returns:
            int: width of text bounding box in px
        """
        return bbox[TextLine.X2] - bbox[TextLine.X1]

    @staticmethod
    def getBboxHeight(bbox):
        """Get the height of the text bounding box

        Args:
            bbox (tuple[int, int, int, int]): text bounding box

        Returns:
            int: height of text bounding box in px
        """
        return bbox[TextLine.Y2] - bbox[TextLine.Y1]

    @staticmethod
    def getBboxSize(bbox):
        """Get the size of a text bounding box.

        Args:
            bbox (tuple[int, int, int, int]): text bounding box

        Returns:
            tuple[int, int]: (width, height) of the text bounding box in px
        """

        return TextLine.getBboxWidth(bbox), TextLine.getBboxHeight(bbox)

    @staticmethod
    def getDescenderMinHeight(textLine):
        """Find the 'actual' size of the descender excluding whitespace.

        Args:
            textLine (TextLine): A TextLine object.

        Returns:
            int: Descender minimum height.
        """
        bboxH = TextLine.getBboxHeight(TextLine.getBbox(textLine))
        txtH = textLine.getSize()[TextLine.HEIGHT]
        offY = textLine.getOffset()[TextLine.Y_OFFSET]

        return bboxH - (txtH - offY)

    @staticmethod
    def getKerningSize(textLine):
        """Get the size of the procceding and trailing kerning for a TextLine Object

        Args:
            textLine (TextLine): TextLine Object

        Returns:
            tuple[int, int]: (left, right) size of kerning in px
        """
        bbox = TextLine.getBbox(textLine)

        left = bbox[TextLine.X1]
        right = textLine.getSize()[TextLine.WIDTH] - bbox[TextLine.X2]

        return left, right

    @staticmethod
    @lru_cache(maxsize=None)
    def getAsciiRange(textLine):
        """Parse TextLine and return it's composition.

        Args:
            textLine (TextLine): TextLine object

        Returns:
            List[int, ...]: ascii composition of TextLine
        """
        text = textLine.getText()
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
    def getSmallestOffY(textLine, asciiRange):
        """Get the smallest offset y, from the range of ascii characters.\n
        This value should be used as an achor point to align text.

        Args:
            textLine (TextLine): A TextLine Object, used to set the font and point of the characters.
            asciiRange (List[int, ...]): Range of ascii characters to test.

        Returns:
            int: Smallest offset y.
        """
        offYSmallest = sys.maxsize

        for char in asciiRange:
            offY = TextLine.copyStyle(textLine, chr(char)).getOffset()[TextLine.Y]
            if offY < offYSmallest:
                offYSmallest = offY

        return offYSmallest

    @staticmethod
    def resize(toResize, toCompare, mode):
        """Resize a TextLine object relative to another.

        Args:
            toResize (TextLine): TextLine being resized.
            toCompare (TextLine): TextLine being compared.
            mode (int): Select which operation you want. (grow, shrink)

        Raises:
            ValueError: Resize mode must match available options.
        """
        if TextLine.SHRINK == mode:
            while (
                toResize.getSize()[TextLine.WIDTH] > toCompare.getSize()[TextLine.WIDTH]
            ):
                newPoint = toResize.getFontPoint() - 1
                toResize.setFontPoint(newPoint)
        elif TextLine.GROW == mode:
            while (
                toResize.getSize()[TextLine.WIDTH] < toCompare.getSize()[TextLine.WIDTH]
            ):
                newPoint = toResize.getFontPoint() + 1
                toResize.setFontPoint(newPoint)
        else:
            raise ValueError("Resize mode not supported.")

    @staticmethod
    def delimitFFmpegPath(filepath):
        """Modifies a filepath to work with FFmpeg.

        Args:
            filepath (str): original filepath

        Returns:
            str: delimited filepath
        """
        return filepath.replace(":", "\\\\:")

    @staticmethod
    def delimitFFmpegText(text):
        """Delimit text, to ensure FFmpeg command runs successfully.

        Args:
            text (str): text

        Returns:
            str: text
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
    def importTextLineToFFmpeg(textLine):
        """Import TextLine into FFmpeg command.

        Args:
            textLine (TextLine): TextLine to import

        Returns:
            list(str, ...): TextLine data being imported
        """
        borderSize = textLine.getBorderSize()
        borderColor = textLine.getBorderColor()
        exportedTextLine = []

        exportedTextLine.extend(
            [
                TextLine.delimitFFmpegPath(textLine.getFontFile()),
                textLine.getFontPoint(),
                textLine.getFontColor(),
                TextLine.delimitFFmpegText(textLine.getText()),
            ]
        )

        exportedTextLine.extend(
            [
                textLine.getPos()[TextLine.X],
                textLine.getPos()[TextLine.Y],
            ]
        )

        if borderSize:
            exportedTextLine.append(borderColor)
            for size in borderSize:
                exportedTextLine.append(size)

        return exportedTextLine

    @staticmethod
    def getFFmpegCMD(imgName, imgPath, textLines, hasBorder, outputDir):
        """Generate the FFmpeg command to draw the textLines onto the image file.

        Args:
            imgName (str): filename of the image (no extension)
            imgPath (str): path of the image
            textLines (list[TextLine, ...]): TextLine Objects
            hasBorder (bool): draw border if True
            outputDir (str): output dir

        Returns:
            str: complete FFmpeg command
        """
        startCmd = '"'
        drawText = "drawtext=fontfile={}:fontsize={}:fontcolor={}:text='{}':x={}:y={}"
        appendBorder = ":boxcolor={}:box=1:boxborderw={}|{}|{}|{}"
        appendCmd = ","
        endCmd = '"'

        # NOTE: textline command with border must be drawn first
        if hasBorder:
            COMPLETE = False
            i = 0
            while not COMPLETE and i < len(textLines):
                if textLines[i].getBorderSize():
                    textLines[i], textLines[0] = textLines[0], textLines[i]
                    COMPLETE = True
                i += 1

        textLineCMDs = []
        for i in range(0, len(textLines)):
            cmdBuilder = ""
            if 0 == i:
                cmdBuilder += startCmd

            cmdBuilder += drawText

            if hasBorder and textLines[i].getBorderSize():
                cmdBuilder += appendBorder

            if textLines[-1] is textLines[i]:
                cmdBuilder += endCmd
            else:
                cmdBuilder += appendCmd

            cmdBuilder = cmdBuilder.format(
                *TextLine.importTextLineToFFmpeg(textLines[i])
            )
            textLineCMDs.append(cmdBuilder)

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

    # constructor
    def __init__(self, text, fontFile, fontPoint, fontColor, img):
        """Initilize TextLine object

        Args:
            text (str): contents of the line
            fontFile (str): path to font
            fontPoint (int): size of font
            fontColor (str): hex color for font
            img (Image): text line position boundary
        """
        # passed
        self.text = text
        self.fontPoint = fontPoint
        self.fontFile = fontFile
        self.fontColor = fontColor
        self.img = img

        # dependent
        self.font = ImageFont.truetype(fontFile, fontPoint)
        self.size = None
        self.offset = None
        self.setSize()

        # uninitilized
        self.position = None  # (x, y) in px
        self.borderSize = None
        self.borderColor = None

    # factory
    @classmethod
    def copyStyle(cls, textLine, text):
        """Create a new TextLine with the same style.

        Args:
            textLine (TextLine): a TextLine Object
            text (str): text

        Returns:
            TextLine: a TextLine Object
        """
        return cls(
            text,
            textLine.getFontFile(),
            textLine.getFontPoint(),
            textLine.getFontColor(),
            textLine.getImg(),
        )

    # getters
    def getText(self):
        """Get text.

        Returns:
            str: text
        """
        return self.text

    def getFontFile(self):
        """Get the font file path.

        Returns:
            str: font file path
        """
        return self.fontFile

    def getFontPoint(self):
        """Get font point.

        Returns:
            int: font point
        """
        return self.fontPoint

    def getFont(self):
        """Get the TextLine font object

        Returns:
            FreeTypeFont: font style used for TextLine
        """
        return self.font

    def getPos(self):
        """Get the TextLine position

        Returns:
            tuple[int, int]: (x, y) anchor point to draw TextLine
        """
        return self.position

    def getImg(self):
        """Get base image

        Returns:
            Image: image text will be drawn on.
        """
        return self.img

    def getImgSize(self):
        """Get image size

        Returns:
            tuple[int, int]: (width, height) in px
        """
        return self.img.size

    def getSize(self):
        """Get the size (including kerning) of the TextLine.\n
        See TextLine.getKerningSize() for more info.

        Returns:
            tuple[int, int]: (width, height) in px
        """
        return self.size

    def getOffset(self):
        """Get the offset needed to draw a TextLine accurately.

        Returns:
            tuple[int, int]: (offset_x, offset_y) indentation from 0, 0 draw point.
        """
        return self.offset

    def getBorderSize(self):
        """Get TextLine border size. If None, then border is disabled.

        Returns:
            tuple[int, int, int, int]: (top, left, bottom, right) width in px
        """
        return self.borderSize

    def getBorderColor(self):
        """Get the border color for the TextLine.

        Returns:
            str: hex color
        """
        return self.borderColor

    def getFontColor(self):
        """Get TextLine font color.

        Returns:
            str: Hex color
        """
        return self.fontColor

    # setters
    def setPos(self, position):
        """Set the TextLine position

        Args:
            position (tuple[int, int]): (x, y) anchor point to draw TextLine

        Raises:
            IndexError: position is out of image bounds
        """
        if (
            0 > position[self.X] > self.img.width
            or 0 > position[self.Y] > self.img.height
        ):
            raise IndexError

        self.position = position

    def setSize(self, consistentHeight=True):
        """Sets the size (width, height) and offset (x, y) of the textLine in px.\n
        Size must be reset every time you change an attribute of the TextLine.

        Args:
            consistentHeight (bool, optional): Should height remain consistant(align all text onto a line). Defaults to True.
        """
        ascent, descent = self.font.getmetrics()
        (textWidth, textHeight), (offset_x, offset_y) = self.font.font.getsize(
            self.text
        )

        if consistentHeight:
            textHeight = ascent
        else:
            # The below is not equivalent to the getSize() textHeight
            textHeight = ascent + descent

        self.size = (textWidth, textHeight)
        self.offset = (offset_x, offset_y)

    def setText(self, text):
        """Change the text for the TextLine.

        Args:
            text (str): text
        """
        self.text = text
        self.setSize()

    def setBorderSize(self, borderSize):
        """Set the TextLine border size.

        Args:
            borderSize (tuple[int, int, int, int]): (top, left, bottom, right) width in px
        """
        self.borderSize = borderSize

    def setBorderColor(self, borderColor):
        """Set the TextLine border color.

        Args:
            borderColor (str): hex color
        """
        self.borderColor = borderColor

    def setFontPoint(self, fontPoint):
        """Set the font point for the TextLine.

        Args:
            fontPoint (int): font point
        """
        self.fontPoint = fontPoint
        self.font = ImageFont.truetype(self.fontFile, fontPoint)
        self.setSize()
