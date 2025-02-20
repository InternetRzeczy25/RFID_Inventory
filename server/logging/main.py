import logging
import sys
from typing import Literal
from logging import _levelToName


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
        return f"{col}{_levelToName[record.levelno]}{self.reset}:     {super().format(record)}"


server_print = logging.StreamHandler(sys.stdout)
server_print.setFormatter(Formatter(fmt="{name} - {message}", style="{"))
server_print.setLevel("INFO")

LEVEL = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def get_configured_logger(name: str, level: LEVEL = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.addHandler(server_print)
    logger.setLevel(level)
    return logger
