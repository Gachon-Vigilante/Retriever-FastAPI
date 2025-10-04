"""MongoDB 스키마 모듈 - 데이터 모델 중앙 집중 내보내기

이 모듈은 MongoDB에서 사용되는 모든 데이터 모델들을 중앙에서 관리하고 내보냅니다.
다른 모듈에서 데이터 모델을 가져올 때 단일 진입점을 제공하여
import 구문을 단순화하고 모듈 구조를 명확하게 합니다.

MongoDB Schema Module - Centralized export of data models

This module centrally manages and exports all data models used in MongoDB.
It provides a single entry point for importing data models from other modules,
simplifying import statements and clarifying module structure.

Examples:
    # 단일 모델 가져오기
    from core.mongo.schemas import Channel, Message, ...

    # 모든 모델 가져오기
    from core.mongo import schemas
    channel = schemas.Channel(...)
    message = schemas.Message(...)
    ...
"""

from .channel import Channel
from .message import Message
from .post import Post, PostFields

__all__ = [
    "Channel",
    "Message",
    "Post", "PostFields",
]