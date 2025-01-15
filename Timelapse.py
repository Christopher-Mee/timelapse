""" Christopher Mee
2025-01-10
Draw a date and time overlay onto images.
"""

import logging
import os
import sys
import time

import CropImages
import DrawTimelapseOverlay
import RenderTimelapseVideo
from LoggingConfig import LoggingConfig
from TextLine import TextLine, RenderEngine

# MODULE-LEVEL LOGGER
LOGGER_NAME = os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(LOGGER_NAME)

# SETTINGS ====================================================================
CROP: bool = True
OVERLAY: bool = True

# advanced
CropImages.RENDER_ENGINE = RenderEngine.PILLOW  # RenderEngine.FFMPEG
DrawTimelapseOverlay.RENDER_ENGINE = RenderEngine.PILLOW  # RenderEngine.FFMPEG
RenderTimelapseVideo.RENDER_ENGINE = RenderEngine.FFMPEG
LOGGING = False
# =============================================================================

# ERROR MSG
SCRIPT_NAME: str = os.path.basename(__file__)

# DEBUG
CropImages.LOGGING = LOGGING
DrawTimelapseOverlay.LOGGING = LOGGING
TextLine.LOGGING = LOGGING
RenderTimelapseVideo.LOGGING = LOGGING


def createTimelapse(inputDir: str) -> None:
    """Create a time-lapse video. Choose whether to crop and/or overlay the
    output video.

    Args:
        inputDir (str): Input folder path.
    """
    if CROP:
        inputDir = CropImages.applyCropToDir(inputDir)

    if OVERLAY:
        inputDir = DrawTimelapseOverlay.applyOverlayToDir(inputDir)

    RenderTimelapseVideo.convertImagesToVideo(inputDir)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python " + SCRIPT_NAME + " <directory_path>")
        sys.exit(1)

    START_TIME = time.time()
    inputDir = sys.argv[1]

    if LOGGING:
        LoggingConfig.setLogToFileConfig()

    createTimelapse(inputDir)

    print("Process finished --- %s seconds ---" % (time.time() - START_TIME))
