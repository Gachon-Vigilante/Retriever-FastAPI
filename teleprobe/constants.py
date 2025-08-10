"""Teleprobe 상수 및 설정 모듈 - 로거 설정과 공통 상수 정의

이 모듈은 Teleprobe 패키지에서 사용되는 로거 설정과 공통 상수들을 정의합니다.
커스텀 로거가 있는 경우 우선 사용하고, 없는 경우 표준 라이브러리의 logging을 사용합니다.

Teleprobe Constants and Configuration Module - Logger setup and common constants definition

This module defines logger configuration and common constants used in the Teleprobe package.
It prioritizes custom logger if available, otherwise falls back to standard library logging.

Constants:
    Logger: 사용할 로거 클래스 또는 함수
           Logger class or function to use
           - CustomLogger (utils.Logger): 커스텀 로거가 있는 경우
                                        When custom logger is available
           - getLogger (logging.getLogger): 표준 로거 함수
                                          Standard logger function

Examples:
    from teleprobe.constants import Logger

    logger = Logger(__name__)
    logger.info("메시지 로깅")

Note:
    이 모듈은 import 시점에 커스텀 로거의 존재 여부를 확인하고,
    적절한 로거를 선택합니다. 실패 시 표준 logging을 사용합니다.

    This module checks for custom logger availability at import time
    and selects appropriate logger. Falls back to standard logging on failure.
"""

from logging import getLogger

try:
    from utils import Logger as CustomLogger
    Logger = CustomLogger
except ImportError:
    Logger = getLogger
    getLogger().debug("Custom logger not found. Using default logger.")
