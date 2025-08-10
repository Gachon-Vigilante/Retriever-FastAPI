import os
from logging import getLogger
from types import TracebackType
from typing import Callable, Mapping

from dotenv import load_dotenv
from .logger_setup import get_customized_logger

load_dotenv()

def get_logger(*args, **kwargs):
    if os.getenv("CUSTOMIZE_UVICORN_LOGGER", "false").lower() == "true":
        return get_customized_logger()
    else:
        return getLogger(*args, **kwargs)

logger = get_logger()

class Logger:
    _logger = logger
    def __init__(self, header: str = None):
        self.header: str
        if header is None:
            self.header = ""
        else:
            self.header = f"[{header}] "

    def log(self, level: int, msg: object, *args: object, **kwargs) -> None:
        self._logger.log(level, f"{self.header} {msg}", *args, **kwargs)

    def debug(self, msg: object, *args: object, **kwargs) -> None:
        self._logger.debug(f"{self.header} {msg}", *args, **kwargs)

    def info(self, msg: object, *args: object, **kwargs) -> None:
        self._logger.info(f"{self.header} {msg}", *args, **kwargs)

    def warning(self, msg: object, *args: object, **kwargs) -> None:
        self._logger.warning(f"{self.header} {msg}", *args, **kwargs)

    def error(self, msg: object, *args: object, **kwargs) -> None:
        self._logger.error(f"{self.header} {msg}", *args, **kwargs)

    def critical(self, msg: object, *args: object, **kwargs) -> None:
        self._logger.critical(f"{self.header} {msg}", *args, **kwargs)

    def exception(self, msg: object, *args: object, **kwargs) -> None:
        self._logger.exception(f"{self.header} {msg}", *args, **kwargs)
