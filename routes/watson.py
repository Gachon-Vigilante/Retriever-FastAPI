from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.mongo.channel import ChannelFields, Channel
from core.mongo.connections import MongoCollections
from teleprobe.errors import ChannelNotFoundError
from utils import Logger
from watson.chat.bot import Watson
from .responses import TeleprobeHTTPException

logger = Logger(__name__)

watson_router = APIRouter(prefix="/api/v1/watson")

class ChatbotAnswer(BaseModel):
    answer: str = Field(
        title="챗봇 응답",
        description="질문에 대한 챗봇의 응답"
    )


@watson_router.get("/c/{channel_identifier}", response_model=ChatbotAnswer)
async def ask_watson(q: str, channel_identifier: str):
    """
    """
    if channel_identifier.isdecimal():
        channel_key = int(channel_identifier)
        result = MongoCollections().channels.find_one({ChannelFields.channel_id: channel_key})
    else:
        result = MongoCollections().channels.find_one({ChannelFields.username: channel_identifier})
    if not result:
        raise TeleprobeHTTPException.from_error(ChannelNotFoundError("질문을 요청한 채널은 현재 발견되지 않았습니다."))

    channel = Channel.from_mongo(result)

    return ChatbotAnswer(answer=await Watson(channels=[channel]).ask(q))
