import logging
import sys
from logging import _levelToName
from typing import Literal

SERVER_LOGGING_LEVEL = "INFO"


class Formatter(logging.Formatter):
    """Custom formatter for logging messages with ANSI color codes"""

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    turquoise = "\033[36;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: turquoise,
        logging.INFO: green,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
    }

    def format(self, record):
        col = self.FORMATS.get(record.levelno, self.grey)
        head = f"{col}{_levelToName[record.levelno]}{self.reset}:"
        return f"{head:22}{super().format(record)}"


server_formatter = Formatter(fmt="{name} - {message}", style="{")

LEVEL = Literal["NOTSET", "DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]


def get_configured_logger(name: str, level: LEVEL = "WARN") -> logging.Logger:
    logger = logging.getLogger(name)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(server_formatter)
    stdout_handler.setLevel(SERVER_LOGGING_LEVEL)
    logger.addHandler(stdout_handler)
    logger.setLevel(level)
    return logger
