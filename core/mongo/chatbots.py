from datetime import datetime
from enum import StrEnum

from bson import ObjectId
from pydantic import Field

from .base import BaseMongoObject
from .connections import MongoCollections


class ChatbotFields(StrEnum):
    """Chatbot 문서 필드 상수"""
    chatbot_id = "chatbot_id"
    channel_ids = "channel_ids"
    created_at = "created_at"
    updated_at = "updated_at"

class Chatbot(BaseMongoObject):
    """"""
    chatbot_id: int = Field(alias=ChatbotFields.chatbot_id)
    channel_ids: list[int] = Field(alias=ChatbotFields.channel_ids)
    created_at: datetime = Field(default_factory=datetime.now, alias=ChatbotFields.created_at)
    updated_at: datetime = Field(default_factory=datetime.now, alias=ChatbotFields.updated_at)

    def store(self) -> ObjectId:
        """문서를 MongoDB에 저장하고 ObjectId를 반환합니다."""
        new_chatbot = self.model_dump()
        MongoCollections().chatbots.insert_one(new_chatbot)
        return new_chatbot.get("_id")

    def update(self):
        MongoCollections().chatbots.update_one(
            filter={"_id": self.oid},
            update={"$set": {ChatbotFields.updated_at: datetime.now()},
                    "$setOnInsert": {
                        ChatbotFields.chatbot_id: self.chatbot_id,
                        ChatbotFields.channel_ids: self.channel_ids,
                        ChatbotFields.created_at: datetime.now()
                    }},
            upsert=True
        )