""" Christopher Mee
2024-12-20
Time-lapse video renderer.
"""

""" WARNING ===================================================================
- Bad color output!
"""

import logging
import os
import subprocess  # FFmpeg
import sys
import threading
import time

from DrawTimelapseOverlay import printProgress
from LoggingConfig import LoggingConfig
from TextLine import RenderEngine

# MODULE-LEVEL LOGGER
LOGGER_NAME = os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(LOGGER_NAME)

# SETTINGS ====================================================================
RENDER_ENGINE = RenderEngine.FFMPEG
FPS = 6
CRF = 18
SPEED = "slow"
PIXEL_FORMAT = "yuv420p"  # Ex: "yuv420p" (8-bit YUV)

# advanced
KEYFRAME_INTERVAL = 2  # time (seconds) between keyframes
PROGRESS_FILE_NAME = "progress.txt"
LOGGING = False
# =============================================================================

# PROGRESS THREAD
TOTAL_FRAMES = 0
FRAMES_RENDERED = 0
LOCK: threading.Lock = threading.Lock()
STOP_EVENT = threading.Event()

# ERROR MSG
SCRIPT_NAME: str = os.path.basename(__file__)

# CACHE
# Only change if errors occur.
RETRY_WAIT = 0.5  # time (seconds) between retries
RETRY_LIMIT = 10  # Maximum retries allowed
RETRY_COUNT = 0


def cleanup(filename: str) -> None:
    """Cleanup working files.

    Args:
        filename (str): File to delete.
    """
    workingPath = os.path.dirname(os.path.abspath(__file__))
    progressFilePath = os.path.join(workingPath, filename)
    if os.path.exists(progressFilePath):
        os.remove(progressFilePath)


def getFFmpegConcatFile(
    inputDir: str, framerate: float, outputFile: str = "filenames.txt"
) -> str:
    """Generate a text file of images and frame durations for FFmpeg concat function.

    Args:
        inputDir (str): Path to the folder containing image files.
        framerate (float): The framerate (fps).
        outputFile (str, optional): The name of the output text file. Defaults to "filenames.txt".

    Raises:
        ValueError: Framerate <= 0.
        FileNotFoundError: Path does not exist.

    Returns:
        int: Output filename (not full path).
    """
    global TOTAL_FRAMES
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    frameDuration = 1 / framerate

    if framerate <= 0:
        raise ValueError("Framerate must be greater than 0.")

    if not os.path.isdir(inputDir):
        raise FileNotFoundError(f"'{inputDir}' is not a valid folder.")

    imageFiles = [
        file
        for file in os.listdir(inputDir)
        if os.path.isfile(os.path.join(inputDir, file))
        and os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS
    ]
    imageFiles.sort()

    TOTAL_FRAMES = len(imageFiles)

    if TOTAL_FRAMES == 0:
        raise FileNotFoundError(f"The directory '{inputDir}' has no images.")

    with open(outputFile, "w") as file:
        for image in imageFiles:
            file.write(f"file '{os.path.join(inputDir, image)}'\n")
            file.write(f"duration {frameDuration:.6f}\n")

    return outputFile


def getFFmpegImageToVideoCMD(
    concatFile: str, fps: float, outputFile: str = "output.mp4"
) -> str:
    """Get FFmpeg command used to convert a folder of images into a video.

    Args:
        concatFile (str): Text file with order of images and frame durations.
        fps (float): Video frames per second.
        outputFile (str, optional): The name of the output video file (including extension). Defaults to "output.mp4".

    Returns:
        str: FFmpeg command.
    """
    return " ".join(
        [
            "ffmpeg",
            "-progress {}".format(PROGRESS_FILE_NAME),
            "-r {}".format(fps),
            "-f concat -safe 0 -i {}".format(concatFile),
            "-c:v libx265 -tag:v hvc1",
            "-crf {} -preset {}".format(CRF, SPEED),
            "-pix_fmt {}".format(PIXEL_FORMAT),
            "-g {}".format(fps * KEYFRAME_INTERVAL),
            "-y",
            "{}".format(outputFile),
        ]
    )


def monitorFFmpegProgress(progressFile: str = PROGRESS_FILE_NAME) -> None:
    """Monitor FFmpeg render progress.

    Args:
        progressFile (str, optional): Input FFmpeg log file. Defaults to "progress.text".
    """
    try:
        with open(progressFile, "r") as file:
            FINISHED = False
            while not FINISHED:
                line = file.readline()
                if line:
                    metric, value = line.strip().split("=", 1)
                    match metric:
                        case "frame":
                            value = int(value)
                            incrementProgress(value)
                        case "progress":
                            if value == "end":
                                incrementProgress(  # set FRAMES_RENDERED = TOTAL_FRAMES
                                    TOTAL_FRAMES
                                )
                                FINISHED = True
                else:
                    time.sleep(0.1)
        cleanup(progressFile)

    except FileNotFoundError:
        global RETRY_COUNT

        if RETRY_COUNT < RETRY_LIMIT and not STOP_EVENT.is_set():
            time.sleep(RETRY_WAIT)
            RETRY_COUNT += 1
            monitorFFmpegProgress()
        else:
            STOP_EVENT.set()
            print(
                f"{LOGGER_NAME} - ERROR: The FFmpeg progress file '{progressFile}' was not found."
            )

    except KeyboardInterrupt:
        print("Monitoring stopped.")


def incrementProgress(framesRendered: int | None) -> None:
    """Increment program progress or set if not constant increase.

    Args:
        framesRendered (int | None): New total value. If None (null), increment existing total value.
    """
    global FRAMES_RENDERED, LOCK

    LOCK.acquire()
    if not framesRendered:
        FRAMES_RENDERED += 1
    elif framesRendered > FRAMES_RENDERED:
        FRAMES_RENDERED = framesRendered
    LOCK.release()


def printRenderProgress() -> None:
    """Thread to track render progress.

    See also:
        `printProgress()`

    Args:
        imagesToRender (int): Total images to render.
    """
    global FRAMES_RENDERED
    COMPLETE = 100

    done = False
    while not done:
        # Order of operations issue caused by threading: divide by zero
        if not (TOTAL_FRAMES == 0):  # !!!ERROR VAR USED HAS CHANGED!!!
            progress = (FRAMES_RENDERED / TOTAL_FRAMES) * 100
        else:
            progress = 0

        printProgress(progress)

        if progress == COMPLETE or STOP_EVENT.is_set():
            done = True


def renderVideo(inputDir: str) -> None:
    """Render images into a video.

    Args:
        inputDir (str): Folder of images to render.
    """
    match RENDER_ENGINE:
        case RenderEngine.FFMPEG:
            try:
                concatFile = getFFmpegConcatFile(inputDir, FPS)
                FFmpegCMD = getFFmpegImageToVideoCMD(concatFile, FPS)

                if LOGGING:
                    logger.debug("Convert images into video: %s", FFmpegCMD)

                subprocess.Popen(
                    FFmpegCMD, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
                ).wait()

                cleanup(concatFile)
            except FileNotFoundError as e:
                STOP_EVENT.set()
                print(f"{LOGGER_NAME} - ERROR: {e}")

        case _:
            raise NotImplementedError("Render engine not supported.")


def convertImagesToVideo(inputDir: str) -> None:
    """Convert folder of images into a video.

    Args:
        inputDir (str): Input folder path.

    Raises:
        FileNotFoundError: Folder path invalid.
    """
    if not os.path.isdir(inputDir):
        raise FileNotFoundError(f"The directory '{inputDir}' does not exist.")

    threads: list[threading.Thread] = []
    try:
        threads.append(
            threading.Thread(
                target=renderVideo,
                args=(inputDir,),
            )
        )

        threads.append(threading.Thread(target=printRenderProgress))
        if RENDER_ENGINE == RenderEngine.FFMPEG:
            threads.append(threading.Thread(target=monitorFFmpegProgress))

        print("Please wait, converting images into video...")
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    except (ValueError, FileNotFoundError) as e:
        STOP_EVENT.set()

        # Overwrite progress bar with error msg using '\r'.
        print(f"{LOGGER_NAME} - ERROR: {e}", end="\r", flush=True)

        for thread in threads:  # cleanup
            thread.join()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python " + SCRIPT_NAME + " <directory_path>")
        sys.exit(1)

    START_TIME = time.time()
    inputDir = sys.argv[1]

    if LOGGING:
        LoggingConfig.setLogToFileConfig()

    convertImagesToVideo(inputDir)

    print()  # progress bar here
    print("Process finished --- %s seconds ---" % (time.time() - START_TIME))
