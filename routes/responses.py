from pydantic import BaseModel, Field
from enum import StrEnum

class ResponseStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"

class Response(BaseModel):
    status: ResponseStatus
    message: str

class SuccessfulResponse(BaseModel):
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: str = Field(default="")
