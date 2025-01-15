"""Christopher Mee
2025-01-13
Debug static methods, such that each file can be debugged individually or all at once.
"""

import logging


class LoggingConfig:

    @staticmethod
    def setLogToFileConfig() -> None:
        """Default configuration for python logging."""
        logging.basicConfig(
            filename="debug.log",
            filemode="w",
            encoding="utf-8",
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%m/%d/%Y %I:%M:%S %p",
        )
        logging.getLogger("PIL").setLevel(logging.WARNING)  # ignore
