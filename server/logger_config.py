import logging
import os
import time


class Ansi:
    """
    ANSI 컬러 및 텍스트 속성 코드를 정의한 클래스.
    터미널에서 텍스트 색상 및 강조 표시를 적용할 때 사용한다.
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
    """
    시간 포맷 및 디렉토리 경로 정보를 포함하는 기본 포맷터입니다.
    다른 Formatter의 상위 클래스 역할을 합니다.
    """

    def formatTime(self, record, date_fmt=None) -> str:
        """
        로그 시간 포맷을 지정한다 (밀리초 포함).

        :param record: 로그 레코드
        :type record: logging.LogRecord
        :param date_fmt: 사용자 정의 시간 포맷 (선택)
        :type date_fmt: str | None
        :return: 포맷된 시간 문자열
        :rtype: str
        """
        ct = self.converter(record.created)
        s = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        return f"{s}.{int(record.msecs):03d}"

    def format(self, record: logging.LogRecord) -> str:
        """
        로그 메시지를 최종 문자열로 포맷합니다.

        :param record: 로그 레코드
        :type record: logging.LogRecord
        :return: 포맷된 로그 메시지
        :rtype: str
        """
        return super().format(record)

    @staticmethod
    def get_directory_format(record: logging.LogRecord) -> str:
        """
        프로젝트 루트를 기준으로 상대 디렉토리 경로를 추출합니다.

        :param record: 로그 레코드
        :type record: logging.LogRecord
        :return: 상대 경로 문자열
        :rtype: str
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
    """
    로그 파일에 저장할 때 사용하는 포맷터.
    """

    def __init__(self, fmt:str=None):
        """
        로그 파일에 저장할 기본 포맷을 설정한다.
        """
        fmt = fmt or "%(asctime)s, %(levelname)s, %(message)s, %(filename)s, %(directory)s"
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        record.directory = self.get_directory_format(record)
        return super().format(record)



class ColorFormatter(BasicFormatter):
    """
    ANSI 컬러를 적용하여 콘솔 출력용 로그 메시지를 포맷하는 포맷터.
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
        """
        컬러 콘솔 로그 출력을 위한 기본 포맷을 설정한다.
        """
        fmt = fmt or Ansi.FG['white'] + "[%(asctime)s] %(levelname)s : %(message)s (%(filename)s in %(directory)s)" + Ansi.RESET
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        """
        로그 메시지에 색상 및 서식을 적용하여 포맷한다.

        :param record: 로그 레코드
        :type record: logging.LogRecord
        :return: 색상이 적용된 포맷 문자열
        :rtype: str
        """
        color = self.COLORS.get(record.levelno, Ansi.FG['white'])
        record.levelname = f"{Ansi.BOLD}{color}{record.levelname:<8}{Ansi.FG['white']}"
        record.msg = f"{Ansi.DEFAULT}{record.msg}{Ansi.FG['white']}"
        record.filename = f"{color}{record.filename}{Ansi.FG['white']}"
        record.directory = f"{Ansi.ITALIC}{self.get_directory_format(record)}{Ansi.FG['white']}"

        return super().format(record)

class AccessLogConsoleFormatter(ColorFormatter):
    """
    HTTP 액세스 로그를 출력할 때 사용하는 포맷터.
    """

    def __init__(self):
        """
        HTTP 액세스 로그를 출력할 때 사용하는 포맷터.
        """
        fmt = Ansi.FG['white'] + "[%(asctime)s] %(levelname)s : %(message)s (HTTP access log)" + Ansi.RESET
        super().__init__(fmt)

class AccessLogFileFormatter(FileFormatter):
    """
    HTTP 액세스 로그 파일에 저장할 때 사용하는 포맷터.
    """

    def __init__(self):
        """
        HTTP 액세스 로그 파일에 저장할 기본 포맷을 설정한다.
        """
        fmt = "%(asctime)s, %(levelname)s, %(message)s, %(filename)s, %(directory)s"
        super().__init__(fmt)
