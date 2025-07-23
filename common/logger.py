import logging
import sys
import pathlib
from logging.handlers import RotatingFileHandler
from typing import Final

LEVEL_COLOURS: Final[dict[int, str]] = {
    logging.DEBUG: "\033[34m",        # blue
    logging.INFO: "\033[32m",         # green
    logging.WARNING: "\033[33m",      # yellow
    logging.ERROR: "\033[31m",        # red
    logging.CRITICAL: "\033[1;41m",   # white on red bg
}
RESET = "\033[0m"
FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


class LogLevelFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        colour = LEVEL_COLOURS.get(record.levelno, "")
        return f"{colour}{base}{RESET}"


def get_logger(name: str, /,
               level: int | str = "INFO",
               disable_ansi: bool = True,
               logfile: pathlib.Path | None = None):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False
    simple_fmt = logging.Formatter(FMT, DATEFMT)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(LogLevelFormatter(FMT, DATEFMT)
                        if not disable_ansi else simple_fmt)
    logger.addHandler(stream)
    if logfile:
        arbitrary_size = 5 * 1024 ** 2
        file = RotatingFileHandler(
            logfile, maxBytes=arbitrary_size, backupCount=3, encoding="utf-8")
        file.setFormatter(simple_fmt)
        logger.addHandler(file)

    return logger
