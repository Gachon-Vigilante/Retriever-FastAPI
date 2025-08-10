from typing import Optional, Dict

from fastapi import HTTPException
from pydantic import BaseModel, Field
from enum import StrEnum

from starlette.status import *

from teleprobe.errors import *

class ResponseStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"

class Response(BaseModel):
    """
    FastAPI에서 사용하는 표준 API 응답 모델입니다.

    상태 코드(`success`, `warning`, `error`)와 설명을 포함하여
    클라이언트에게 일관된 메시지를 전달할 수 있도록 합니다.

    Attributes:
        status (ResponseStatus): 응답 상태를 나타냅니다.
        message (Optional[str]): 상태에 대한 상세 설명입니다. 생략 가능.
    """
    status: ResponseStatus
    message: Optional[str] = Field(default=None)

class SuccessfulResponse(BaseModel):
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: Optional[str] = Field(default=None)

class TeleprobeHTTPException:
    _exception_code_map: Dict[type[Exception], int]= {
        NotChannelError: HTTP_400_BAD_REQUEST,
        ChannelNotFoundError: HTTP_404_NOT_FOUND,
        ChannelKeyInvalidError: HTTP_400_BAD_REQUEST,
        ChannelAlreadyWatchedError: HTTP_409_CONFLICT,
        ChannelNotWatchedError: HTTP_404_NOT_FOUND,
        UsernameNotFoundError: HTTP_404_NOT_FOUND,
        ConnectionError: HTTP_503_SERVICE_UNAVAILABLE,
    }
    _exception_detail_map: Dict[type[Exception], str]= {
        ConnectionError: "텔레그램 서비스에 연결할 수 없는 상태입니다."
    }
    @classmethod
    def from_error(
            cls,
            e: Exception,
            status_code: int = None,
            detail: Optional[str] = None,
            extra_status_code_map: Optional[Dict[type[Exception], int]] = None,
            extra_detail_map: Optional[Dict[type[Exception], str]] = None,
    ):
        exception_type = e.__class__
        status_code_map = cls._exception_code_map.copy()
        status_code_map.update(extra_status_code_map or {})
        detail_map = cls._exception_detail_map.copy()
        detail_map.update(extra_detail_map or {})

        if not status_code and exception_type in status_code_map:
            status_code = status_code_map[exception_type]
        if not detail and exception_type in detail_map:
            detail = detail_map[exception_type]

        # exception map 또는 extra에 이미 정의된 예외
        if status_code:
            raise HTTPException(
                status_code=status_code,
                detail=detail or getattr(e, "message", str(e))
            )
        # 예상하지 못한 예외
        else:
            raise e
