"""API 응답 모델 모듈 - FastAPI 애플리케이션의 표준 응답 및 예외 처리

이 모듈은 FastAPI 애플리케이션에서 사용되는 표준 HTTP 응답 모델들과
예외 처리 유틸리티를 제공합니다. 일관된 API 응답 형식을 보장하고,
Teleprobe 특화 예외들을 HTTP 상태 코드로 매핑하는 기능을 포함합니다.

API Response Model Module - Standard responses and exception handling for FastAPI application

This module provides standard HTTP response models and exception handling utilities
used in the FastAPI application. It ensures consistent API response formats and
includes functionality to map Teleprobe-specific exceptions to HTTP status codes.
"""

from typing import Optional, Dict

from fastapi import HTTPException
from pydantic import BaseModel, Field
from enum import StrEnum

from starlette.status import *

from teleprobe.errors import *

class ResponseStatus(StrEnum):
    """API 응답 상태를 나타내는 문자열 열거형

    모든 API 응답에서 사용되는 표준 상태 값들을 정의합니다.
    클라이언트가 응답의 성공/실패 여부를 명확하게 구분할 수 있도록 합니다.

    String enumeration representing API response status

    Defines standard status values used in all API responses.
    Enables clients to clearly distinguish success/failure of responses.

    Attributes:
        SUCCESS (str): 요청이 성공적으로 처리됨
                      Request processed successfully
        FAILURE (str): 요청 처리 중 실패 발생
                      Failure occurred during request processing
    """
    SUCCESS = "success"
    FAILURE = "failure"

class Response(BaseModel):
    """FastAPI 애플리케이션에서 사용하는 표준 API 응답 모델

    모든 API 엔드포인트에서 일관된 응답 형식을 제공하기 위한 기본 모델입니다.
    응답 상태와 선택적 메시지를 포함하여 클라이언트에게 처리 결과를
    명확하게 전달합니다.

    Standard API response model used in FastAPI application

    Base model for providing consistent response format across all API endpoints.
    Includes response status and optional message to clearly communicate
    processing results to clients.

    Attributes:
        status (ResponseStatus): 응답 상태 (성공/실패)
                               Response status (success/failure)
        message (Optional[str]): 응답에 대한 상세 설명 (선택적)
                               Detailed description of the response (optional)

    Examples:
        # 성공 응답
        response = Response(status=ResponseStatus.SUCCESS, message="작업이 완료되었습니다.")

        # 실패 응답
        response = Response(status=ResponseStatus.FAILURE, message="오류가 발생했습니다.")

        # 메시지 없는 응답
        response = Response(status=ResponseStatus.SUCCESS)
    """
    status: ResponseStatus
    message: Optional[str] = Field(default=None)

class SuccessfulResponse(BaseModel):
    """성공적인 API 응답을 위한 특화된 응답 모델

    성공 상태가 기본값으로 설정된 응답 모델입니다.
    성공 케이스에서 반복적으로 상태를 지정할 필요 없이 간편하게 사용할 수 있습니다.

    Specialized response model for successful API responses

    Response model with success status set as default value.
    Can be used conveniently in success cases without repeatedly specifying status.

    Attributes:
        status (ResponseStatus): 성공 상태로 고정됨 (ResponseStatus.SUCCESS)
                               Fixed to success status (ResponseStatus.SUCCESS)
        message (Optional[str]): 성공에 대한 상세 설명 (선택적)
                               Detailed description of success (optional)

    Examples:
        # 기본 성공 응답
        response = SuccessfulResponse()

        # 메시지가 포함된 성공 응답
        response = SuccessfulResponse(message="사용자가 성공적으로 생성되었습니다.")
    """
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: Optional[str] = Field(default=None)

class TeleprobeHTTPException:
    """Teleprobe 특화 예외를 HTTP 예외로 변환하는 유틸리티 클래스

    Teleprobe 애플리케이션에서 발생하는 도메인 특화 예외들을
    적절한 HTTP 상태 코드와 메시지로 변환하여 FastAPI에서 처리할 수 있도록 합니다.
    예외 타입별로 상태 코드와 메시지를 매핑하는 기능을 제공합니다.

    Utility class for converting Teleprobe-specific exceptions to HTTP exceptions

    Converts domain-specific exceptions that occur in the Teleprobe application
    to appropriate HTTP status codes and messages for processing in FastAPI.
    Provides functionality to map status codes and messages by exception type.

    Class Attributes:
        _exception_code_map (Dict): 예외 타입과 HTTP 상태 코드의 매핑
                                  Mapping between exception types and HTTP status codes
        _exception_detail_map (Dict): 예외 타입과 상세 메시지의 매핑
                                    Mapping between exception types and detailed messages

    Examples:
        try:
            # Teleprobe 로직 실행
            some_teleprobe_operation()
        except SomeCustomError as e:
            TeleprobeHTTPException.from_error(e)

    Note:
        지원되는 예외 타입들:
        - NotChannelError -> 400 Bad Request
        - ChannelNotFoundError -> 404 Not Found
        - ConnectionError -> 503 Service Unavailable

        Supported exception types:
        - NotChannelError -> 400 Bad Request
        - ChannelNotFoundError -> 404 Not Found  
        - ConnectionError -> 503 Service Unavailable
    """
    _exception_code_map: Dict[type[Exception], int]= {
        NotChannelError: HTTP_400_BAD_REQUEST,
        ChannelNotFoundError: HTTP_404_NOT_FOUND,
        ChannelKeyInvalidError: HTTP_400_BAD_REQUEST,
        ChannelAlreadyWatchedError: HTTP_409_CONFLICT,
        ChannelNotWatchedError: HTTP_404_NOT_FOUND,
        UsernameNotFoundError: HTTP_404_NOT_FOUND,
        ConnectionError: HTTP_503_SERVICE_UNAVAILABLE,
        ChannelNotJoinedError: HTTP_403_FORBIDDEN,
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
        """예외 객체를 FastAPI HTTPException으로 변환하는 클래스 메서드

        주어진 예외를 분석하여 적절한 HTTP 상태 코드와 메시지를 결정하고,
        FastAPI에서 처리할 수 있는 HTTPException으로 변환합니다.
        추가 매핑을 통해 기본 매핑을 확장할 수 있습니다.

        Class method to convert exception objects to FastAPI HTTPException

        Analyzes given exceptions to determine appropriate HTTP status codes and messages,
        and converts them to HTTPException that can be handled by FastAPI.
        Default mappings can be extended through additional mappings.

        Args:
            e (Exception): 변환할 원본 예외 객체
                          Original exception object to convert
            status_code (Optional[int]): 강제로 지정할 상태 코드
                                       Status code to force override
            detail (Optional[str]): 강제로 지정할 상세 메시지
                                   Detail message to force override
            extra_status_code_map (Optional[Dict]): 추가 상태 코드 매핑
                                                  Additional status code mappings
            extra_detail_map (Optional[Dict]): 추가 상세 메시지 매핑
                                             Additional detail message mappings

        Raises:
            HTTPException: 예외가 매핑에 정의된 경우 적절한 상태 코드로 발생
                          Raised with appropriate status code if exception is defined in mapping
            Exception: 매핑에 정의되지 않은 예외인 경우 원본 예외를 다시 발생
                      Re-raises original exception if not defined in mapping

        Examples:
            # 기본 변환
            TeleprobeHTTPException.from_error(ChannelNotFoundError("채널을 찾을 수 없습니다"))

            # 추가 매핑과 함께 변환
            extra_codes = {CustomError: 422}
            TeleprobeHTTPException.from_error(some_error, extra_status_code_map=extra_codes)
        """
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
