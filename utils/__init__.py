import os
from logging import getLogger

from dotenv import load_dotenv

from .logger_setup import get_customized_logger

load_dotenv()

class Logger:
    def __new__(cls, *args, **kwargs):
        if os.getenv("CUSTOMIZE_LOGGER", "false").lower() == "true":
            if args:
                return get_customized_logger(args[0])
            elif kwargs and (name := kwargs.get("name")):
                return get_customized_logger(name)
            else:
                return get_customized_logger()
        else:
            return getLogger(*args, **kwargs)
