""" Christopher Mee
2025-01-05
Crop image into standard 16:9 display resolution.
"""

""" WARNINGS ==================================================================
- FFmpeg will change the color of your input image. However, it is faster 
than Pillow, use at your own discretion.
"""

import logging
import math
import os
import subprocess  # FFmpeg
import sys
import threading
import time
from enum import Enum

from PIL import Image, ImageFile

from DrawTimelapseOverlay import countImages, printProgress
from LoggingConfig import LoggingConfig
from TextLine import RenderEngine


class HorizontalCrop(Enum):
    "Image crop in the horizontal axis."
    LEFT = 0
    RIGHT = 1
    CENTER = 2


class VerticalCrop(Enum):
    "Image crop in the vertical axis."
    TOP = 0
    BOTTOM = 1
    CENTER = 2


class CropType(Enum):
    "Cropping method."
    ASPECT_RATIO = 0
    RESOLUTION = 1


# MODULE-LEVEL LOGGER
LOGGER_NAME = os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(LOGGER_NAME)

# RESOLUTIONS =================================================================
DISPLAY_RES = [  # Add all resolutions here
    (3840, 2160),  # 4K UHD
    (2560, 1440),  # 1440p QHD
    (1920, 1080),  # 1080p FHD
    (1280, 720),  # 720p HD
    (854, 480),  # 480p SD
    (640, 360),  # 360p
    (426, 240),  # 240p
]
QHD, WHD, FHD, HD = range(4)  # Add all resolution aliases (in order) here
# =============================================================================

# SETTINGS ====================================================================
RENDER_ENGINE = RenderEngine.FFMPEG

# cropping
CROP_POSITION: tuple[VerticalCrop, HorizontalCrop] = (
    VerticalCrop.TOP,
    HorizontalCrop.CENTER,
)
CROP_TYPE = CropType.ASPECT_RATIO

# scaling
DOWNSCALE: bool = True
DOWNSCALE_RES: tuple[int, int] | None = DISPLAY_RES[FHD]

# advanced
LOGGING = False
# =============================================================================

# DISPLAY RESOLUTION
RES_WIDTH, RES_HEIGHT = range(2)

# CROP
VERTICAL_CROP, HORIZONTAL_CROP = range(2)
LEFT, TOP, RIGHT, BOTTOM = range(4)

# ASPECT RATIO
# Dont change ratio unless you swap out the display resolutions as well.
WIDESCREEN_RATIO: tuple[int, int] = (16, 9)
RATIO_WIDTH, RATIO_HEIGHT = range(2)

# THREADING
IMAGES_CROPPED: int = 0
LOCK: threading.Lock = threading.Lock()
STOP_EVENT = threading.Event()

# ERROR MSG
SCRIPT_NAME: str = os.path.basename(__file__)


def getStandardRes(imageSize: tuple[int, int]) -> tuple[int, int] | None:
    """Determines the highest standard 16:9 display resolution that fits within
    the given image dimensions.

    Args:
        imageSize (tuple[int, int]): Image size (`WIDTH`, `HEIGHT`), in px.

    Returns:
        tuple[int, int] | None: Best-fit standard resolution (`WIDTH`, `HEIGHT`),
        in px. If None (null), no standard resolution found.
    """
    for width, height in DISPLAY_RES:
        if width <= imageSize[RES_WIDTH] and height <= imageSize[RES_HEIGHT]:
            return (width, height)
    return None


def verticalCrop(
    image: Image.Image, cropHeight: float, cropBbox: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """Calculate vertical image crop.

    Args:
        image (Image.Image): Image to crop.
        cropHeight (float): Height of crop, in px.
        cropBbox (tuple[int, int, int, int]): Existing crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`), to be modified.

    Raises:
        ValueError: Vertical crop position not supported.

    Returns:
        tuple[int, int, int, int]: New crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`).
    """
    left = cropBbox[LEFT]
    top = cropBbox[TOP]
    right = cropBbox[RIGHT]
    bottom = cropBbox[BOTTOM]

    match (CROP_POSITION[VERTICAL_CROP]):
        case VerticalCrop.TOP:
            top = 0
            bottom = int(cropHeight)
        case VerticalCrop.BOTTOM:
            top = int(image.height - cropHeight)
            bottom = image.height
        case VerticalCrop.CENTER:
            marginCrop = (image.height - cropHeight) / 2
            top = math.floor(marginCrop)
            bottom = image.height - math.ceil(marginCrop)
        case _:
            raise ValueError("Vertical crop position invalid!")

    return (left, top, right, bottom)


def horizontalCrop(
    image: Image.Image, cropWidth: float, cropBbox: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """Calculate horizontal image crop.

    Args:
        image (Image.Image): Image to crop.
        cropWidth (float): Width of crop, in px.
        cropBbox (tuple[int, int, int, int]): Existing crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`), to be modified.

    Raises:
        ValueError: Horizontal crop position not supported.

    Returns:
        tuple[int, int, int, int]: New crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`).
    """
    left = cropBbox[LEFT]
    top = cropBbox[TOP]
    right = cropBbox[RIGHT]
    bottom = cropBbox[BOTTOM]

    match (CROP_POSITION[HORIZONTAL_CROP]):
        case HorizontalCrop.LEFT:
            left = 0
            right = int(cropWidth)
        case HorizontalCrop.RIGHT:
            left = image.width - int(cropWidth)
            right = image.width
        case HorizontalCrop.CENTER:
            marginCrop = (image.width - cropWidth) / 2
            left = math.floor(marginCrop)
            right = image.width - math.ceil(marginCrop)
        case _:
            raise ValueError("Horizontal crop position invalid!")

    return (left, top, right, bottom)


def aspectRatioCrop(image: Image.Image) -> tuple[int, int, int, int]:
    """Calculate image crop by using aspect ratio. (Only crops image height.)

    Args:
        image (Image.Image): Image to crop.

    Raises:
        ValueError: Vertical crop position not set.

    Returns:
        tuple[int, int, int, int]: Crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`).
    """
    if CROP_POSITION[VERTICAL_CROP] == None:
        raise ValueError("Need vertical crop position to proceed!")
    cropHeight = (
        image.width * WIDESCREEN_RATIO[RATIO_HEIGHT] / WIDESCREEN_RATIO[RATIO_WIDTH]
    )
    return verticalCrop(image, cropHeight, (0, 0, image.width, 0))


def resolutionCrop(
    image: Image.Image, cropRes: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Calculate image crop by using resolution.

    Args:
        image (Image.Image): Image to crop.
        cropRes (tuple[int, int]): Resolution of crop (`WIDTH`, `HEIGHT`), in px.

    Returns:
        tuple[int, int, int, int]: Crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`).
    """
    return horizontalCrop(
        image,
        cropRes[RES_WIDTH],
        verticalCrop(image, cropRes[RES_HEIGHT], (0, 0, 0, 0)),
    )


def renderCrop(
    imageFile: ImageFile.ImageFile,
    cropBbox: tuple[int, int, int, int],
    standardRes: tuple[int, int],
    outputPath: str,
) -> None:
    """Thread which crops image and increments total crop progress.

    Args:
        imageFile (ImageFile.ImageFile): Image to crop.
        cropBbox (tuple[int, int, int, int]): Crop bbox (`LEFT`,`RIGHT`,`TOP`,`BOTTOM`).
        standardRes (tuple[int, int]): Best-fit standard resolution (`WIDTH`, `HEIGHT`),
        in px.
        outputPath (str): Output path.

    Raises:
        ValueError: Render Engine not supported.
    """
    match RENDER_ENGINE:
        case RenderEngine.PILLOW:
            modifiedImage: Image.Image = imageFile.crop(cropBbox)
            if DOWNSCALE and modifiedImage.size > standardRes:
                modifiedImage = modifiedImage.resize(
                    DOWNSCALE_RES if DOWNSCALE_RES else standardRes,
                    Image.Resampling.LANCZOS,
                )
            modifiedImage.save(outputPath, "PNG")

        case RenderEngine.FFMPEG:
            cropWidth = cropBbox[RIGHT] - cropBbox[LEFT]
            cropHeight = cropBbox[BOTTOM] - cropBbox[TOP]
            cropX = cropBbox[LEFT]
            cropY = cropBbox[TOP]

            formatFilter = ""
            if (  # fix color shift when converting from .jpg to .png
                os.path.splitext(imageFile.filename)[1].lower() == ".jpg"
                and os.path.splitext(outputPath)[1].lower() == ".png"
            ):
                FFMPEG_PIXEL_FORMAT = "gbrp"
                formatFilter = f"format={FFMPEG_PIXEL_FORMAT}"

            cropFilter = f"crop={cropWidth}:{cropHeight}:{cropX}:{cropY}"

            resizeFilter = ""
            if DOWNSCALE and imageFile.size > standardRes:
                targetRes = DOWNSCALE_RES if DOWNSCALE_RES else standardRes
                resizeFilter = f"scale={targetRes[RES_WIDTH]}:{targetRes[RES_HEIGHT]}:flags=lanczos"

            # add all video filters to this list
            videoFilters = [formatFilter, cropFilter, resizeFilter]

            FFmpegCMD = " ".join(
                [
                    "ffmpeg",
                    '-i "{}"'.format(imageFile.filename),
                    '-vf "{}"'.format(
                        ", ".join(filter for filter in videoFilters if filter)
                    ),
                    "-y",
                    '"{}"'.format(outputPath),
                ]
            )

            if LOGGING:
                logger.debug("Cropping image - %s", FFmpegCMD)

            subprocess.Popen(
                FFmpegCMD,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            ).wait()

        case _:
            raise ValueError("Render engine not supported!")

    incCropProgress()


def cropImage(inputDir: str, filename: str, outputDir: str) -> threading.Thread:
    """Crop an image using your choice of render engine.

    Args:
        inputDir (str): Input folder path.
        filename (str): Image name (with file extension).
        outputDir (str): Output folder path.

    Raises:
        ValueError: Cannot crop, resolution too small.
        ValueError: Crop type not supported.

    Returns:
        threading.Thread: Running crop render thread.
    """
    IMG_EXT = ".png"
    imgPath = os.path.join(inputDir, filename)
    imgName = os.path.splitext(filename)[0]  # Remove file extension
    image = Image.open(imgPath)

    os.makedirs(outputDir, exist_ok=True)
    outputPath = os.path.join(outputDir, imgName + IMG_EXT)

    standardRes = getStandardRes(image.size)
    if not standardRes:
        raise ValueError("Cannot crop image, resolution too small!")

    match CROP_TYPE:
        case CropType.ASPECT_RATIO:
            cropBbox = aspectRatioCrop(image)
        case CropType.RESOLUTION:
            cropBbox = resolutionCrop(image, standardRes)
        case _:
            raise ValueError("Crop type unsupported!")

    cropRenderer = threading.Thread(
        target=renderCrop,
        args=(
            image,
            cropBbox,
            standardRes,
            outputPath,
        ),
    )
    cropRenderer.start()

    return cropRenderer


def incCropProgress() -> None:
    """Increment total crop progress."""
    global IMAGES_CROPPED, LOCK

    LOCK.acquire()
    IMAGES_CROPPED += 1
    LOCK.release()


def printCropProgress(imagesToCrop: int) -> None:
    """Thread to track total crop progress.

    See also:
        `printProgress()`

    Args:
        imagesToCrop (int): Total images to crop.
    """
    global IMAGES_CROPPED
    COMPLETE = 100

    done = False
    while not done:
        progress = (IMAGES_CROPPED / imagesToCrop) * 100
        printProgress(progress)
        if progress == COMPLETE or STOP_EVENT.is_set():
            done = True


def applyCropToDir(inputDir: str) -> str:
    """Apply a crop to all images in the directory.

    Args:
        inputDir (str): Input folder path

    Raises:
        FileNotFoundError: Input folder path does not exist.

    Returns:
        str: Output folder path.
    """
    if not os.path.isdir(inputDir):
        raise FileNotFoundError(f"The directory '{inputDir}' does not exist.")

    outputDir = os.path.join(inputDir, "output")
    os.makedirs(outputDir, exist_ok=True)

    cropProgress = threading.Thread(
        target=printCropProgress,
        args=(countImages(inputDir),),
    )
    print("Please wait, cropping images...")
    cropProgress.start()

    cropRenderers: list[threading.Thread] = []
    for filename in os.listdir(inputDir):
        if (
            filename.endswith(".jpg")
            or filename.endswith(".jpeg")
            or filename.endswith(".png")
        ):
            try:
                cropRenderers.append(cropImage(inputDir, filename, outputDir))
            except Exception as e:
                STOP_EVENT.set()  # Stop progress thread
                time.sleep(0.01)
                print("Error cropping images: " + str(e))
                break  # exit program

    for cropRenderer in cropRenderers:
        cropRenderer.join()

    if cropRenderers:
        cropProgress.join()

    return outputDir


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python " + SCRIPT_NAME + " <directory_path>")
        sys.exit(1)

    START_TIME = time.time()
    inputDir = sys.argv[1]

    if LOGGING:
        LoggingConfig.setLogToFileConfig()

    applyCropToDir(inputDir)

    print()  # PROGRESS BAR HERE
    print("Process finished --- %s seconds ---" % (time.time() - START_TIME))
