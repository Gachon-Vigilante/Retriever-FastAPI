import os
from logging import getLogger

from dotenv import load_dotenv
from .logger_setup import get_customized_logger

load_dotenv()

def get_logger(*args, **kwargs):
    if os.getenv("CUSTOMIZE_UVICORN_LOGGER", "false").lower() == "true":
        return get_customized_logger()
    else:
        return getLogger(*args, **kwargs)