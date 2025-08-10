"""로그 포맷터 및 색상 설정 모듈 - 커스텀 로깅 시스템의 시각적 구성

이 모듈은 로그 메시지의 포맷팅과 색상 표시를 담당하는 다양한 포맷터 클래스들을 제공합니다.
ANSI 색상 코드를 활용한 콘솔 출력, 파일 저장용 포맷팅, HTTP 접근 로그 전용 포맷터 등
다양한 출력 형태에 최적화된 로그 포맷터들을 포함합니다.

Log Formatter and Color Configuration Module - Visual configuration for custom logging system

This module provides various formatter classes responsible for log message formatting and color display.
It includes log formatters optimized for various output forms such as console output using ANSI color codes,
file storage formatting, and HTTP access log dedicated formatters.
"""

import logging
import os
import time


class Ansi:
    """ANSI 색상 및 텍스트 속성 코드를 정의하는 상수 클래스

    터미널에서 텍스트 색상과 강조 표시를 적용하기 위한 ANSI 이스케이프 시퀀스들을 정의합니다.
    로그 메시지의 색상 구분과 텍스트 스타일 적용에 사용되며, 다양한 색상과 스타일 옵션을 제공합니다.

    Constant class defining ANSI color and text attribute codes

    Defines ANSI escape sequences for applying text colors and emphasis in terminals.
    Used for color distinction in log messages and text style application, providing various color and style options.

    Attributes:
        RESET (str): 모든 스타일과 색상을 초기화하는 코드
                    Code to reset all styles and colors
        BOLD (str): 굵은 글씨 스타일 코드
                   Bold text style code
        ITALIC (str): 기울임 글씨 스타일 코드
                     Italic text style code
        INVERSE (str): 색상 반전 스타일 코드
                      Color inversion style code
        FG (dict): 기본 전경색 코드들
                  Basic foreground color codes
        BR_FG (dict): 밝은 전경색 코드들
                     Bright foreground color codes
        DEFAULT (str): 기본 스타일 (리셋 + 밝은 흰색)
                      Default style (reset + bright white)

    Examples:
        # 빨간색 텍스트
        red_text = f"{Ansi.BR_FG['red']}Error message{Ansi.RESET}"

        # 굵은 파란색 텍스트
        bold_blue = f"{Ansi.BOLD}{Ansi.BR_FG['blue']}Info message{Ansi.RESET}"

        # 기본 스타일로 초기화
        text = f"{Ansi.DEFAULT}Normal text"

    Note:
        색상 지원 여부는 터미널 환경에 따라 달라질 수 있습니다.
        Windows Command Prompt에서는 ANSI 색상 지원이 제한적일 수 있습니다.

        Color support may vary depending on terminal environment.
        ANSI color support may be limited in Windows Command Prompt.
    """
    RESET = '\033[0m'
    BOLD = '\033[1m'
    ITALIC = '\033[3m'
    INVERSE = '\033[7m'

    # 전경색 (foreground)
    FG = {
        'white': '\033[37m',
    }

    # 밝은(bright) 전경색
    BR_FG = {
        'white': '\033[97m',
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m'
    }

    DEFAULT = RESET + BR_FG['white']


PROJECT_ROOT = str(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class BasicFormatter(logging.Formatter):
    """로그 포맷팅을 위한 기본 포맷터 클래스

    시간 포맷팅과 디렉토리 경로 처리 등의 공통 기능을 제공하는 기본 포맷터입니다.
    다른 전문화된 포맷터들의 상위 클래스 역할을 하며, 밀리초까지 포함한 정확한 시간 표시와
    프로젝트 루트를 기준으로 한 상대 경로 표시 기능을 제공합니다.

    Base formatter class for log formatting

    Basic formatter providing common functionality such as time formatting and directory path processing.
    Serves as parent class for other specialized formatters, providing accurate time display including milliseconds
    and relative path display based on project root.

    Methods:
        formatTime: 밀리초를 포함한 시간 포맷팅
                   Time formatting including milliseconds
        format: 로그 레코드를 문자열로 포맷팅
               Format log record to string
        get_directory_format: 프로젝트 기준 상대 경로 추출
                             Extract relative path based on project

    Examples:
        # 직접 사용보다는 상속받아 사용
        class CustomFormatter(BasicFormatter):
            def __init__(self):
                super().__init__("%(asctime)s - %(message)s")

    Note:
        이 클래스는 주로 상속 목적으로 설계되었으며,
        직접 인스턴스화하여 사용하기보다는 하위 클래스를 통해 사용됩니다.

        This class is mainly designed for inheritance purposes
        and is used through subclasses rather than direct instantiation.
    """

    def formatTime(self, record, date_fmt=None) -> str:
        """로그 시간을 밀리초까지 포함하여 포맷팅하는 메서드

        표준 logging.Formatter의 formatTime을 재정의하여 밀리초까지 포함한
        정확한 시간 정보를 제공합니다. YYYY-MM-DD HH:MM:SS.mmm 형식을 사용합니다.

        Method to format log time including milliseconds

        Overrides standard logging.Formatter's formatTime to provide accurate time information
        including milliseconds. Uses YYYY-MM-DD HH:MM:SS.mmm format.

        Args:
            record (logging.LogRecord): 포맷팅할 로그 레코드
                                      Log record to format
            date_fmt (Optional[str]): 사용자 정의 날짜 포맷 (현재 무시됨)
                                    Custom date format (currently ignored)

        Returns:
            str: 밀리초까지 포함된 포맷된 시간 문자열
                Formatted time string including milliseconds

        Examples:
            # 결과 예시: "2024-01-15 14:30:25.123"
            formatted_time = formatter.formatTime(record)

        Note:
            date_fmt 매개변수는 현재 구현에서 사용되지 않으며,
            항상 고정된 형식으로 시간을 포맷팅합니다.

            date_fmt parameter is not used in current implementation
            and always formats time in fixed format.
        """
        ct = self.converter(record.created)
        s = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        return f"{s}.{int(record.msecs):03d}"

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 최종 문자열로 포맷팅하는 메서드

        부모 클래스의 format 메서드를 호출하여 로그 레코드를 문자열로 변환합니다.
        하위 클래스에서 추가적인 처리를 위해 재정의할 수 있는 확장 지점을 제공합니다.

        Method to format log record to final string

        Calls parent class's format method to convert log record to string.
        Provides extension point that can be overridden by subclasses for additional processing.

        Args:
            record (logging.LogRecord): 포맷팅할 로그 레코드
                                      Log record to format

        Returns:
            str: 포맷팅된 로그 메시지 문자열
                Formatted log message string

        Examples:
            formatter = BasicFormatter("%(asctime)s - %(message)s")
            formatted_msg = formatter.format(log_record)
        """
        return super().format(record)

    @staticmethod
    def get_directory_format(record: logging.LogRecord) -> str:
        """프로젝트 루트를 기준으로 상대 디렉토리 경로를 추출하는 정적 메서드

        로그가 발생한 파일의 디렉토리 경로를 프로젝트 루트 기준의 상대 경로로 변환합니다.
        절대 경로를 간결한 상대 경로로 표시하여 로그의 가독성을 향상시킵니다.

        Static method to extract relative directory path based on project root

        Converts directory path of file where log occurred to relative path based on project root.
        Improves log readability by displaying absolute paths as concise relative paths.

        Args:
            record (logging.LogRecord): 경로 정보를 추출할 로그 레코드
                                      Log record to extract path information from

        Returns:
            str: 프로젝트 루트 기준 상대 경로
                Relative path based on project root

        Examples:
            # 프로젝트 루트인 경우
            path = get_directory_format(record)  # Returns: "\\"

            # 하위 디렉토리인 경우
            path = get_directory_format(record)  # Returns: "\\utils"

            # 프로젝트 외부 경로인 경우
            path = get_directory_format(record)  # Returns: 원본 절대 경로

        Note:
            경로 처리 규칙:
            - 프로젝트 루트와 동일한 경우: "\\" 반환
            - 프로젝트 루트의 하위 경로인 경우: 상대 경로 반환
            - 프로젝트 외부 경로인 경우: 원본 절대 경로 반환

            Path processing rules:
            - If same as project root: return "\\"
            - If subdirectory of project root: return relative path
            - If outside project: return original absolute path
        """
        # 현재 로그가 발생한 코드 파일 경로의 디렉토리 절대경로 산출
        directory = os.path.dirname(record.pathname)
        # 절대경로가 프로젝트 ROOT의 하위 경로일 경우 프로젝트에서의 하위 경로만 표시
        if directory == PROJECT_ROOT:
            directory = "\\"
        elif directory.lower().startswith(PROJECT_ROOT.lower()):
            directory = directory[len(PROJECT_ROOT):]

        return directory


class FileFormatter(BasicFormatter):
    """파일 저장용 로그 포맷터 클래스

    로그를 파일에 저장할 때 사용하는 포맷터입니다.
    색상 코드 없이 구조화된 형태로 로그를 저장하여 파일 크기를 최적화하고
    나중에 분석하기 용이한 형태로 로그를 구성합니다.

    Log formatter class for file storage

    Formatter used when saving logs to files.
    Saves logs in structured format without color codes to optimize file size
    and compose logs in format that's easy to analyze later.

    Attributes:
        기본 포맷: "%(name)s, %(asctime)s, %(levelname)s, %(message)s, %(filename)s, %(directory)s"
        Default format: "%(name)s, %(asctime)s, %(levelname)s, %(message)s, %(filename)s, %(directory)s"

    Examples:
        # 기본 파일 포맷터
        formatter = FileFormatter()

        # 커스텀 포맷으로 파일 포맷터
        formatter = FileFormatter("%(asctime)s - %(levelname)s - %(message)s")

    Note:
        파일 포맷터의 특징:
        - ANSI 색상 코드 미포함
        - CSV 형태의 구조화된 출력
        - 디렉토리 정보 포함
        - 분석 도구로 처리 용이

        File formatter features:
        - No ANSI color codes
        - Structured output in CSV-like format
        - Includes directory information
        - Easy to process with analysis tools
    """

    def __init__(self, fmt:str=None):
        """파일 포맷터를 초기화하는 생성자

        파일 저장에 최적화된 기본 포맷을 설정하거나 사용자 정의 포맷을 적용합니다.
        기본 포맷은 CSV 형태로 구성되어 있어 나중에 분석하기 용이합니다.

        Constructor to initialize file formatter

        Sets default format optimized for file storage or applies custom format.
        Default format is composed in CSV-like format for easy analysis later.

        Args:
            fmt (Optional[str]): 사용자 정의 로그 포맷 문자열
                               Custom log format string
                               None인 경우 기본 포맷 사용
                               Uses default format if None

        Examples:
            # 기본 포맷 사용
            formatter = FileFormatter()

            # 커스텀 포맷 사용
            formatter = FileFormatter("%(asctime)s | %(levelname)s | %(message)s")
        """
        fmt = fmt or "%(name)s, %(asctime)s, %(levelname)s, %(message)s, %(filename)s, %(directory)s"
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드에 디렉토리 정보를 추가하여 포맷팅하는 메서드

        부모 클래스의 format 메서드를 호출하기 전에 레코드에 directory 속성을 추가합니다.
        이를 통해 로그 포맷 문자열에서 %(directory)s 플레이스홀더를 사용할 수 있게 됩니다.

        Method to format log record by adding directory information

        Adds directory attribute to record before calling parent class's format method.
        This enables use of %(directory)s placeholder in log format string.

        Args:
            record (logging.LogRecord): 포맷팅할 로그 레코드
                                      Log record to format

        Returns:
            str: 디렉토리 정보가 포함된 포맷된 로그 문자열
                Formatted log string with directory information included

        Examples:
            # 결과 예시:
            # "mymodule, 2024-01-15 14:30:25.123, INFO, Hello World, main.py, \\src"
            formatted = formatter.format(record)
        """
        record.directory = self.get_directory_format(record)
        return super().format(record)



class ColorFormatter(BasicFormatter):
    """콘솔 출력용 컬러 로그 포맷터 클래스

    ANSI 색상 코드를 사용하여 콘솔에 색상이 적용된 로그를 출력하는 포맷터입니다.
    로그 레벨에 따라 다른 색상을 적용하여 로그의 중요도를 시각적으로 구분할 수 있게 합니다.

    Color log formatter class for console output

    Formatter that outputs colored logs to console using ANSI color codes.
    Applies different colors based on log levels to visually distinguish log importance.

    Attributes:
        COLORS (dict): 로그 레벨별 색상 매핑
                      Color mapping by log level
                      - DEBUG: 파란색 (blue)
                      - INFO: 초록색 (green)
                      - WARNING: 노란색 (yellow)
                      - ERROR: 빨간색 (red)
                      - CRITICAL: 자홍색 (magenta)

    Examples:
        # 기본 컬러 포맷터
        formatter = ColorFormatter()

        # 커스텀 포맷으로 컬러 포맷터
        formatter = ColorFormatter("[%(levelname)s] %(message)s")

    Note:
        색상 표시는 터미널 환경에 따라 달라질 수 있으며,
        일부 환경에서는 색상이 제대로 표시되지 않을 수 있습니다.

        Color display may vary depending on terminal environment,
        and colors may not display properly in some environments.
    """

    # 로그 레벨에 따라 색상을 지정.
    COLORS = {
        logging.DEBUG: Ansi.BR_FG['blue'],
        logging.INFO: Ansi.BR_FG['green'],
        logging.WARNING: Ansi.BR_FG['yellow'],
        logging.ERROR: Ansi.BR_FG['red'],
        logging.CRITICAL: Ansi.BR_FG['magenta'],
    }

    def __init__(self, fmt:str=None):
        """컬러 포맷터를 초기화하는 생성자

        콘솔 출력에 최적화된 컬러 포맷을 설정합니다.
        기본 포맷은 시간, 레벨, 로거명, 메시지, 파일 정보를 포함하며 색상이 적용됩니다.

        Constructor to initialize color formatter

        Sets color format optimized for console output.
        Default format includes time, level, logger name, message, file info with colors applied.

        Args:
            fmt (Optional[str]): 사용자 정의 로그 포맷 문자열
                               Custom log format string
                               None인 경우 기본 컬러 포맷 사용
                               Uses default color format if None

        Examples:
            # 기본 컬러 포맷 사용
            formatter = ColorFormatter()

            # 커스텀 컬러 포맷 사용
            formatter = ColorFormatter(f"{Ansi.BR_FG['green']}[%(levelname)s] %(message)s{Ansi.RESET}")
        """
        fmt = fmt or Ansi.FG['white'] + "[%(asctime)s] %(levelname)s : [%(name)s] %(message)s (%(filename)s in %(directory)s)" + Ansi.RESET
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드에 색상과 스타일을 적용하여 포맷팅하는 메서드

        로그 레벨에 따라 적절한 색상을 선택하고, 각 구성 요소에 색상과 스타일을 적용합니다.
        레벨명, 로거명, 메시지, 파일명, 디렉토리 등 각각에 다른 스타일을 적용하여
        시각적으로 구분하기 쉽게 만듭니다.

        Method to format log record by applying colors and styles

        Selects appropriate color based on log level and applies colors and styles to each component.
        Applies different styles to level name, logger name, message, filename, directory etc.
        to make them visually distinguishable.

        Args:
            record (logging.LogRecord): 포맷팅할 로그 레코드
                                      Log record to format

        Returns:
            str: 색상과 스타일이 적용된 포맷된 로그 문자열
                Formatted log string with colors and styles applied

        Examples:
            # 색상이 적용된 출력 예시:
            # [2024-01-15 14:30:25.123] INFO     : [mymodule] Hello World (main.py in \src)
            formatted = formatter.format(record)

        Note:
            각 구성 요소별 스타일:
            - levelname: 굵게 + 레벨별 색상 + 8자리 좌측 정렬
            - name: 굵게 + 레벨별 색상
            - msg: 기본 스타일
            - filename: 레벨별 색상
            - directory: 기울임 + 기본 흰색

            Styles by component:
            - levelname: Bold + level color + 8-character left alignment
            - name: Bold + level color
            - msg: Default style
            - filename: Level color
            - directory: Italic + default white
        """
        color = self.COLORS.get(record.levelno, Ansi.FG['white'])
        record.levelname = f"{Ansi.BOLD}{color}{record.levelname:<8}{Ansi.FG['white']}"
        record.name = f"{Ansi.BOLD}{color}{record.name}{Ansi.FG['white']}"
        record.msg = f"{Ansi.DEFAULT}{record.msg}{Ansi.FG['white']}"
        record.filename = f"{color}{record.filename}{Ansi.FG['white']}"
        record.directory = f"{Ansi.ITALIC}{self.get_directory_format(record)}{Ansi.FG['white']}"

        return super().format(record)

class AccessLogConsoleFormatter(ColorFormatter):
    """HTTP 접근 로그 전용 콘솔 포맷터 클래스

    HTTP 서버의 접근 로그를 콘솔에 출력할 때 사용하는 특화된 포맷터입니다.
    일반 애플리케이션 로그와 구분하여 HTTP 접근 로그임을 명시하는 간단한 형태로 출력합니다.

    Console formatter class dedicated to HTTP access logs

    Specialized formatter used when outputting HTTP server access logs to console.
    Outputs in simple format that clearly indicates it's HTTP access log, distinguished from general application logs.

    Examples:
        # HTTP 접근 로그 콘솔 포맷터
        formatter = AccessLogConsoleFormatter()

        # 출력 예시:
        # [2024-01-15 14:30:25.123] INFO     : GET /api/users 200 (HTTP access log)

    Note:
        이 포맷터는 주로 uvicorn.access 로거와 함께 사용되며,
        HTTP 요청/응답 정보를 간결하게 표시합니다.

        This formatter is mainly used with uvicorn.access logger
        and displays HTTP request/response information concisely.
    """

    def __init__(self):
        """HTTP 접근 로그 콘솔 포맷터를 초기화하는 생성자

        HTTP 접근 로그에 특화된 간단한 포맷을 설정합니다.
        시간, 레벨, 메시지와 함께 "HTTP access log" 식별자를 포함합니다.

        Constructor to initialize HTTP access log console formatter

        Sets simple format specialized for HTTP access logs.
        Includes time, level, message along with "HTTP access log" identifier.

        Examples:
            formatter = AccessLogConsoleFormatter()
            # 포맷: "[시간] 레벨 : 메시지 (HTTP access log)"
        """
        fmt = Ansi.FG['white'] + "[%(asctime)s] %(levelname)s : %(message)s (HTTP access log)" + Ansi.RESET
        super().__init__(fmt)

class AccessLogFileFormatter(FileFormatter):
    """HTTP 접근 로그 전용 파일 포맷터 클래스

    HTTP 서버의 접근 로그를 파일에 저장할 때 사용하는 특화된 포맷터입니다.
    일반 애플리케이션 로그보다 간소한 형태로 저장하여 접근 로그 분석에 최적화합니다.

    File formatter class dedicated to HTTP access logs

    Specialized formatter used when saving HTTP server access logs to files.
    Saves in more concise format than general application logs, optimized for access log analysis.

    Examples:
        # HTTP 접근 로그 파일 포맷터
        formatter = AccessLogFileFormatter()

        # 출력 예시:
        # 2024-01-15 14:30:25.123, INFO, GET /api/users 200, uvicorn.py, \logs

    Note:
        이 포맷터는 로거 이름(name) 필드를 제외하여
        접근 로그 분석에 불필요한 정보를 줄입니다.

        This formatter excludes logger name field
        to reduce unnecessary information for access log analysis.
    """

    def __init__(self):
        """HTTP 접근 로그 파일 포맷터를 초기화하는 생성자

        HTTP 접근 로그 파일 저장에 최적화된 간단한 포맷을 설정합니다.
        로거명을 제외하고 시간, 레벨, 메시지, 파일명, 디렉토리 정보만 포함합니다.

        Constructor to initialize HTTP access log file formatter

        Sets simple format optimized for HTTP access log file storage.
        Includes only time, level, message, filename, directory information, excluding logger name.

        Examples:
            formatter = AccessLogFileFormatter()
            # 포맷: "시간, 레벨, 메시지, 파일명, 디렉토리"
        """
        fmt = "%(asctime)s, %(levelname)s, %(message)s, %(filename)s, %(directory)s"
        super().__init__(fmt)
