from enum import StrEnum
from typing import Optional

from pydantic import BaseModel


class ResponseStatus(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class Response(BaseModel):
    """
    FastAPI에서 사용하는 표준 API 응답 모델입니다.

    상태 코드(`success`, `warning`, `error`)와 설명을 포함하여
    클라이언트에게 일관된 메시지를 전달할 수 있도록 합니다.

    Attributes:
        status (ResponseStatus): 응답 상태를 나타냅니다.
        description (Optional[str]): 상태에 대한 상세 설명입니다. 생략 가능.
    """
    status: ResponseStatus
    description: Optional[str] = None # 현재 응답 상태에 대한 설명