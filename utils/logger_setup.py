import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Literal

from core.constants import LOG_PATH
from .logger_config import FileFormatter, ColorFormatter, AccessLogConsoleFormatter, AccessLogFileFormatter

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def get_file_handler(formatter = None) -> RotatingFileHandler:
    """
    로그 파일에 기록하는 RotatingFileHandler를 생성한다.

    :return: 로그 파일 핸들러 (회전 로그 방식)
    :rtype: logging.handlers.RotatingFileHandler
    """
    handler = RotatingFileHandler(LOG_PATH, maxBytes=10_000_000, backupCount=5, encoding='utf-8')
    handler.setFormatter(formatter or FileFormatter())
    return handler


def get_console_handler(formatter = None) -> logging.StreamHandler:
    """
    콘솔에 컬러 로그를 출력하는 StreamHandler를 생성한다.

    :return: 콘솔 출력 핸들러
    :rtype: logging.StreamHandler
    """
    handler = logging.StreamHandler()
    handler.setFormatter(formatter or ColorFormatter())
    return handler


def setup_logger(
        name: str = None,
        file_handler: logging.Handler = None,
        console_handler: logging.StreamHandler = None,
        level: int = logging.DEBUG
) -> logging.Logger:
    """
    지정된 이름의 로거를 설정하고 핸들러를 추가한다.

    :param name: 로거 이름. None이면 root 로거를 설정한다.
    :type name: str
    :param file_handler: 파일 저장 시 지정할 핸들러
    :type file_handler: logging.Handler
    :param console_handler: 콘솔 출력 시 지정할 핸들러
    :type console_handler: logging.StreamHandler
    :param level: 로깅 레벨 (예: logging.DEBUG)
    :type level: int
    :return: 설정된 로거 인스턴스
    :rtype: logging.Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    if file_handler:
        logger.addHandler(file_handler)
    if console_handler:
        logger.addHandler(console_handler)
    logger.propagate = False
    return logger

setup_logger("uvicorn", get_file_handler(), get_console_handler())
setup_logger(
    "uvicorn.access",
    get_file_handler(AccessLogFileFormatter()),
    get_console_handler(AccessLogConsoleFormatter())
)

def get_customized_logger(
        name: str = "uvicorn" # "uvicorn", "uvicorn.error", "uvicorn.access" 등
):
    logger = logging.getLogger(name) # logger 구하기
    setup_logger(name, get_file_handler(), get_console_handler()) # handler를 setup해서 반환
    
    return logger

