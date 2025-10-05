"""유틸리티 패키지 - 로깅 시스템 및 공통 유틸리티 모듈

이 패키지는 애플리케이션 전반에서 사용되는 공통 유틸리티 기능들을 제공합니다.
주로 로깅 시스템의 커스터마이징과 관련된 기능들을 포함하며,
환경 변수를 통해 표준 로깅과 커스텀 로깅 시스템을 선택적으로 사용할 수 있습니다.

Utility Package - Logging system and common utility modules

This package provides common utility functionalities used throughout the application.
It mainly includes functionality related to logging system customization,
and allows selective use of standard logging or custom logging systems through environment variables.

Modules:
    logger_setup: 로거 설정 및 핸들러 구성 모듈
                 Logger configuration and handler setup module
    logger_config: 로그 포맷터 및 색상 설정 모듈
                  Log formatter and color configuration module

Classes:
    Logger: 환경 변수에 따라 표준 또는 커스텀 로거를 제공하는 팩토리 클래스
           Factory class providing standard or custom logger based on environment variables

Environment Variables:
    CUSTOMIZE_LOGGER: "true"로 설정 시 커스텀 로거 사용, 기본값은 표준 로거
                     Use custom logger when set to "true", defaults to standard logger

Examples:
    # 환경 변수 설정 (선택적)
    os.environ["CUSTOMIZE_LOGGER"] = "true"

    # 로거 생성
    from utils import Logger
    logger = Logger(__name__)
    logger.info("메시지 로깅")

    # 또는 이름 지정
    logger = Logger("custom_logger_name")
"""

import os
from logging import getLogger

from dotenv import load_dotenv

from .logger_setup import get_customized_logger

load_dotenv()

class Logger:
    """환경 설정에 따라 표준 또는 커스텀 로거를 제공하는 팩토리 클래스

    CUSTOMIZE_LOGGER 환경 변수의 값에 따라 표준 Python logging 모듈의 getLogger 함수 또는
    커스터마이징된 로거를 반환합니다. 이를 통해 애플리케이션 전체에서 일관된 로깅 인터페이스를
    제공하면서도 필요에 따라 고급 로깅 기능을 선택적으로 사용할 수 있습니다.

    Factory class providing standard or custom logger based on environment configuration

    Returns either standard Python logging module's getLogger function or customized logger
    based on CUSTOMIZE_LOGGER environment variable value. This provides consistent logging interface
    throughout the application while allowing selective use of advanced logging features when needed.

    Environment Variables:
        CUSTOMIZE_LOGGER (str): 커스텀 로거 사용 여부를 결정하는 환경 변수
                               Environment variable determining whether to use custom logger
                               - "true" (case-insensitive): 커스텀 로거 사용
                               - 기타 값 또는 미설정: 표준 로거 사용

    Examples:
        # 표준 로거 사용 (기본값)
        logger = Logger(__name__)
        logger.info("표준 로거로 메시지 출력")

        # 커스텀 로거 사용 (환경 변수 설정 필요)
        os.environ["CUSTOMIZE_LOGGER"] = "true"
        logger = Logger(__name__)
        logger.info("커스텀 로거로 메시지 출력")

        # 키워드 인수로 이름 지정
        logger = Logger(name="my_logger")

        # 인수 없이 사용
        logger = Logger()

    Note:
        이 클래스는 __new__ 메서드를 사용하여 실제 로거 객체를 반환하므로,
        Logger 클래스의 인스턴스가 아닌 실제 로거 객체가 생성됩니다.

        This class uses __new__ method to return actual logger objects,
        so actual logger objects are created instead of Logger class instances.
    """

    def __new__(cls, *args, **kwargs):
        """환경 설정에 따라 적절한 로거를 생성하여 반환하는 팩토리 메서드

        CUSTOMIZE_LOGGER 환경 변수를 확인하여 커스텀 로거 또는 표준 로거를 선택합니다.
        전달된 인수들을 적절한 로거 생성 함수에 전달하여 로거 객체를 생성합니다.

        Factory method that creates and returns appropriate logger based on environment configuration

        Checks CUSTOMIZE_LOGGER environment variable to choose between custom logger or standard logger.
        Passes provided arguments to appropriate logger creation function to create logger object.

        Args:
            *args: 로거 생성에 사용할 위치 인수들
                  Positional arguments for logger creation
            **kwargs: 로거 생성에 사용할 키워드 인수들
                     Keyword arguments for logger creation

        Returns:
            logging.Logger: 생성된 로거 객체
                           Created logger object

        Examples:
            # 위치 인수로 이름 전달
            logger = Logger("my_module")

            # 키워드 인수로 이름 전달
            logger = Logger(name="my_module")

            # 인수 없이 사용 (루트 로거 또는 기본 로거)
            logger = Logger()

        Note:
            커스텀 로거 사용 시:
            - args가 있으면 첫 번째 인수를 로거 이름으로 사용
            - kwargs에 'name' 키가 있으면 해당 값을 로거 이름으로 사용
            - 둘 다 없으면 기본 로거 생성

            When using custom logger:
            - If args exist, use first argument as logger name
            - If kwargs has 'name' key, use its value as logger name
            - If neither exists, create default logger
        """
        if os.getenv("CUSTOMIZE_LOGGER", "false").lower() == "true":
            if args:
                return get_customized_logger(args[0])
            elif kwargs and (name := kwargs.get("name")):
                return get_customized_logger(name)
            else:
                return get_customized_logger()
        else:
            return getLogger(*args, **kwargs)
