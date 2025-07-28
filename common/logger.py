import logging
import sys
import pathlib
from logging.handlers import RotatingFileHandler
from typing import Final, Optional, TextIO
from common.constants import get_project_root

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


def try_parse_log_level(value: Optional[str]) -> int:
    if not value:
        return logging.INFO
    return getattr(logging, value.upper(), logging.INFO)


class EnsureLogger:
    def __init__(self, name: str):
        self.name = name
        self._logger: Optional[logging.Logger] = None

    def _ensure_logger(self):
        if self._logger is None:
            self._logger = get_log_manager().get_logger(self.name)

    def __getattr__(self, item):
        self._ensure_logger()
        return getattr(self._logger, item)


class LogManager:
    def __init__(self,
                 default_level: str = "INFO",
                 default_logfile: Optional[pathlib.Path] = None,
                 use_colors: bool = True):
        self.default_level = self.parse_level(default_level)
        self.default_logfile = default_logfile
        self.use_colors = use_colors
        self.component_config: dict[str, dict] = {}
        self._cache: dict[str, logging.Logger] = {}

    def configure_component(self,
                            name: str,
                            level: Optional[str] = None,
                            logfile: Optional[str] = None,
                            ansi: Optional[bool] = None) -> None:
        """Override log settings for a specific component/module."""
        if logfile:
            log_path: pathlib.Path = pathlib.Path(logfile)
            logfile = log_path if log_path.is_absolute() else get_project_root() / log_path
        self.component_config[name] = {
            "level": self.parse_level(level) if level else self.default_level,
            "logfile": logfile or self.default_logfile,
            "ansi": self.use_colors if ansi is None else ansi
        }
        if name in self._cache:
            # invalidate logger on reconfiguration
            del self._cache[name]

    def get_logger(self,
                   name: str) -> logging.Logger:
        """Get (and configure) a logger for a component / module"""
        if name in self._cache:
            return self._cache[name]

        config = self.component_config.get(name, {})
        level = config.get("level", self.default_level)
        logfile = config.get("logfile", self.default_logfile)
        ansi = config.get("ansi", self.use_colors)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = False

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(
            LogLevelFormatter(FMT, DATEFMT) if ansi else logging.Formatter(FMT, DATEFMT))
        logger.addHandler(stream_handler)

        if logfile:
            arbitrary_file_size = 5 * 1024 ** 2
            file_handler = RotatingFileHandler(
                logfile,
                maxBytes=arbitrary_file_size,
                backupCount=3,
                encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(FMT, DATEFMT))
            logger.addHandler(file_handler)

        self._cache[name] = logger
        return logger

    def print_config(self, stream: TextIO = sys.stdout) -> None:
        """Prints the current logging configuration to the given stream."""
        print("LogManager configuration:", file=stream)
        print(f"  Global level  : {logging.getLevelName(self.default_level)}", file=stream)
        print(f"  Global logfile: {self.default_logfile}", file=stream)
        print(f"  ANSI colors   : {self.use_colors}", file=stream)
        if not self.component_config:
            print("  No module overrides configured.", file=stream)
        else:
            print("  Module overrides:", file=stream)
            for name, conf in self.component_config.items():
                print(f"    - {name}:", file=stream)
                print(f"        level  : {logging.getLevelName(conf['level'])}", file=stream)
                print(f"        logfile: {conf['logfile']}", file=stream)
                print(f"        ansi   : {conf['ansi']}", file=stream)

    @staticmethod
    def parse_level(level: Optional[str]) -> int:
        if not level:
            return logging.INFO
        return getattr(logging, level.upper(), logging.INFO)


def get_log_manager() -> LogManager:
    cache_key = "_LOG_MANAGER"
    global_vars = globals()
    if cache_key not in global_vars or not isinstance(global_vars[cache_key], LogManager):
        global_vars[cache_key] = LogManager(
            default_level="INFO",
            use_colors=True)
    return global_vars[cache_key]
