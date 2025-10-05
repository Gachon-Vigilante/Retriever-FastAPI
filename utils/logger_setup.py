"""로거 설정 및 핸들러 구성 모듈 - 커스텀 로깅 시스템의 핵심 설정

이 모듈은 애플리케이션의 로깅 시스템을 설정하고 관리하는 핵심 기능을 제공합니다.
파일 핸들러, 콘솔 핸들러, 로거 설정 등을 통해 일관된 로깅 인터페이스를 구성하며,
회전 로그 파일 관리와 색상이 적용된 콘솔 출력을 지원합니다.

Logger Setup and Handler Configuration Module - Core configuration for custom logging system

This module provides core functionality for setting up and managing the application's logging system.
It configures consistent logging interface through file handlers, console handlers, and logger setup,
supporting rotating log file management and colored console output.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Literal

from core.constants import LOG_PATH
from .logger_config import FileFormatter, ColorFormatter, AccessLogConsoleFormatter, AccessLogFileFormatter

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def get_file_handler(formatter = None) -> RotatingFileHandler:
    """회전 로그 파일에 기록하는 핸들러를 생성하는 함수

    지정된 경로에 로그 파일을 생성하고, 파일 크기가 한계에 도달하면 자동으로 백업 파일을 생성합니다.
    최대 5개의 백업 파일을 유지하며, UTF-8 인코딩을 사용하여 한글 로그를 올바르게 처리합니다.

    Function to create handler for writing to rotating log files

    Creates log files at specified path and automatically creates backup files when file size reaches limit.
    Maintains up to 5 backup files and uses UTF-8 encoding to properly handle Korean logs.

    Args:
        formatter (Optional[logging.Formatter]): 사용할 로그 포맷터 (기본값: FileFormatter)
                                               Log formatter to use (default: FileFormatter)

    Returns:
        RotatingFileHandler: 구성된 회전 파일 핸들러
                           Configured rotating file handler

    Examples:
        # 기본 포맷터로 파일 핸들러 생성
        handler = get_file_handler()

        # 커스텀 포맷터로 파일 핸들러 생성
        custom_formatter = FileFormatter("%(asctime)s - %(message)s")
        handler = get_file_handler(custom_formatter)

    Note:
        파일 핸들러 설정:
        - 최대 파일 크기: 10MB (10,000,000 bytes)
        - 백업 파일 수: 5개
        - 인코딩: UTF-8
        - 로그 파일 경로: core.constants.LOG_PATH에서 정의

        File handler configuration:
        - Maximum file size: 10MB (10,000,000 bytes)
        - Number of backup files: 5
        - Encoding: UTF-8
        - Log file path: Defined in core.constants.LOG_PATH
    """
    handler = RotatingFileHandler(LOG_PATH, maxBytes=10_000_000, backupCount=5, encoding='utf-8')
    handler.setFormatter(formatter or FileFormatter())
    return handler


def get_console_handler(formatter = None) -> logging.StreamHandler:
    """색상이 적용된 콘솔 출력 핸들러를 생성하는 함수

    표준 출력(stdout)에 로그를 출력하는 핸들러를 생성합니다.
    기본적으로 ColorFormatter를 사용하여 로그 레벨에 따른 색상 구분을 제공합니다.

    Function to create console output handler with color support

    Creates handler that outputs logs to standard output (stdout).
    Uses ColorFormatter by default to provide color distinction based on log levels.

    Args:
        formatter (Optional[logging.Formatter]): 사용할 로그 포맷터 (기본값: ColorFormatter)
                                               Log formatter to use (default: ColorFormatter)

    Returns:
        logging.StreamHandler: 구성된 콘솔 출력 핸들러
                              Configured console output handler

    Examples:
        # 기본 색상 포맷터로 콘솔 핸들러 생성
        handler = get_console_handler()

        # 커스텀 포맷터로 콘솔 핸들러 생성
        custom_formatter = ColorFormatter("[%(levelname)s] %(message)s")
        handler = get_console_handler(custom_formatter)

    Note:
        색상 지원:
        - DEBUG: 파란색
        - INFO: 초록색
        - WARNING: 노란색
        - ERROR: 빨간색
        - CRITICAL: 자홍색

        Color support:
        - DEBUG: Blue
        - INFO: Green
        - WARNING: Yellow
        - ERROR: Red
        - CRITICAL: Magenta
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
    """로거를 설정하고 핸들러를 연결하는 함수

    지정된 이름의 로거를 생성하거나 가져와서 핸들러들을 연결하고 로깅 레벨을 설정합니다.
    기존 핸들러들을 모두 제거한 후 새로운 핸들러들을 추가하여 깔끔한 로거 구성을 보장합니다.

    Function to configure logger and attach handlers

    Creates or retrieves logger with specified name, attaches handlers, and sets logging level.
    Removes all existing handlers before adding new ones to ensure clean logger configuration.

    Args:
        name (Optional[str]): 로거 이름 (None인 경우 루트 로거)
                            Logger name (root logger if None)
        file_handler (Optional[logging.Handler]): 파일 출력용 핸들러
                                                 Handler for file output
        console_handler (Optional[logging.StreamHandler]): 콘솔 출력용 핸들러
                                                          Handler for console output
        level (int): 로깅 레벨 (기본값: logging.DEBUG)
                    Logging level (default: logging.DEBUG)

    Returns:
        logging.Logger: 구성된 로거 인스턴스
                       Configured logger instance

    Examples:
        # 파일과 콘솔 핸들러가 모두 있는 로거
        logger = setup_logger(
            name="my_logger",
            file_handler=get_file_handler(),
            console_handler=get_console_handler(),
            level=logging.INFO
        )

        # 콘솔 출력만 하는 로거
        logger = setup_logger(
            name="console_only",
            console_handler=get_console_handler()
        )

    Note:
        로거 설정 특징:
        - propagate=False로 설정하여 상위 로거로의 전파 방지
        - 기존 핸들러 모두 제거 후 새 핸들러 추가
        - 핸들러가 None인 경우 해당 출력은 비활성화

        Logger configuration features:
        - Set propagate=False to prevent propagation to parent loggers
        - Remove all existing handlers before adding new ones
        - Disable corresponding output if handler is None
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
    """커스터마이징된 로거를 생성하고 반환하는 함수

    지정된 이름의 로거를 가져와서 파일 핸들러와 콘솔 핸들러를 설정합니다.
    기본적으로 파일과 콘솔 양쪽에 모두 출력하도록 구성되며, 색상과 포맷팅이 적용됩니다.

    Function to create and return customized logger

    Retrieves logger with specified name and configures file and console handlers.
    Configured by default to output to both file and console with color and formatting applied.

    Args:
        name (str): 로거 이름 (기본값: "uvicorn")
                   Logger name (default: "uvicorn")
                   - "uvicorn": 일반 애플리케이션 로그
                   - "uvicorn.access": HTTP 접근 로그
                   - "uvicorn.error": 오류 전용 로그
                   - 사용자 정의 이름도 가능

    Returns:
        logging.Logger: 완전히 구성된 커스텀 로거
                       Fully configured custom logger

    Examples:
        # 기본 로거 (uvicorn)
        logger = get_customized_logger()
        logger.info("기본 로거 메시지")

        # HTTP 접근 로그 로거
        access_logger = get_customized_logger("uvicorn.access")
        access_logger.info("HTTP 접근 로그")

        # 사용자 정의 로거
        custom_logger = get_customized_logger("my_module")
        custom_logger.debug("사용자 정의 로거 메시지")

    Note:
        이 함수로 생성된 로거는:
        - 파일과 콘솔에 동시 출력
        - 회전 로그 파일 지원 (10MB 제한, 5개 백업)
        - 콘솔에서 색상 구분 지원
        - UTF-8 인코딩으로 한글 지원

        Loggers created by this function:
        - Output to both file and console simultaneously
        - Support rotating log files (10MB limit, 5 backups)
        - Support color distinction in console
        - Support Korean with UTF-8 encoding
    """
    logger = logging.getLogger(name) # logger 구하기
    setup_logger(name, get_file_handler(), get_console_handler()) # handler를 setup해서 반환
    
    return logger

