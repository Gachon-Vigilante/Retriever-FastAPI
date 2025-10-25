"""텔레그램 채널 수집 태스크 모듈

이 모듈은 텔레그램 채널 식별자(링크/username/채널ID)를 입력받아 채널 정보를 수집·저장하고,
모니터링 시작 요청을 FastAPI로 전달한 뒤, 채널 메시지를 순회하여 MongoDB에 저장하는
Celery 태스크를 제공합니다. 분석 파이프라인에서 식별된 텔레그램 identifier 후처리를 자동화합니다.

비즈니스 규칙:
- 채널 조회 시 ChannelHandler를 통해 MongoDB/Neo4j 저장을 수행합니다.
- posts.analysis.promotions[].identifiers[]의 경로(mongo_path)가 주어지면, 해당 identifier에
  매핑된 channel_id와 처리 상태(is_processed)를 업데이트합니다.
- 예상 가능(허용)한 Telethon 오류는 MongoDB에 error 메시지로 기록하고 처리 완료로 표시합니다.

환경 변수:
- FASTAPI_HOST: FastAPI 서버 베이스 URL (예: http://localhost:8000)

기능 변경 없이 문서화만 추가합니다.
"""
import asyncio
import os
from urllib.parse import urljoin

import requests
from bson import ObjectId
from celery import shared_task
from pymongo import ReturnDocument

from core.constants import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING
from core.mongo.connections import MongoCollections
from core.mongo.post import PostFields
from core.neo4j.ogm import PostNode, ChannelNode, Promotes
from handlers import ChannelHandler, MessageHandler
from teleprobe import TeleprobeClient
from teleprobe.errors import ACCEPTABLE_EXCEPTIONS
from utils import Logger
from ..names import TELEGRAM_CHANNEL_TASK_NAME

logger = Logger(__name__)


@shared_task(name=TELEGRAM_CHANNEL_TASK_NAME)
def telegram_channel_task(channel_identifier: str, post_id: str | None = None, mongo_path: str | None = None):
    """텔레그램 채널을 수집/모니터링하고 관련 MongoDB 문서를 갱신하는 Celery 태스크

    Args:
        channel_identifier (str): 텔레그램 채널 식별자(링크/username/채널ID).
        post_id (str | None): identifier를 포함한 posts 문서의 ObjectId 문자열(선택).
        mongo_path (str | None): identifier의 경로(예: analysis.promotions.0.identifiers.1)(선택).

    Returns:
        None

    Note:
        - post_id와 mongo_path가 함께 제공되면, identifier에 연결된 channel_id를 기록하고
          is_processed를 True로 변경합니다.
        - 허용된 Telethon 예외(ACCEPTABLE_EXCEPTIONS)는 error 필드에 메시지를 기록한 뒤
          is_processed를 True로 전환합니다.
    """
    logger.info(f"Collecting telegram channel key: {channel_identifier}")
    if post_id:
        post_id = ObjectId(post_id)

    async def _run():
        post_collection = MongoCollections().posts
        try:
            async with TeleprobeClient(
                    api_id=TELEGRAM_API_ID,
                    api_hash=TELEGRAM_API_HASH,
                    session_string=TELEGRAM_SESSION_STRING
            ) as client:
                # 채널 정보 조회 (비동기 방식)
                logger.info(f"채널 정보 수집 및 모니터링을 시도합니다. channel key: {channel_identifier}")
                channel = await client.get_channel(channel_identifier, ChannelHandler()) # 채널 정보 수집 후 저장
                logger.info(f"채널 정보를 수집(또는 업데이트)했습니다. channel key: {channel_identifier}")
                if post_id and mongo_path:
                    result = post_collection.find_one_and_update(
                        filter={"_id": post_id},
                        update={"$set": {mongo_path+".channel_id": channel.channel_id}},
                        projection={"_id": 1, PostFields.link: 1},
                        return_document=ReturnDocument.AFTER
                    )
                    Promotes.merge(
                        post=PostNode.from_mongo(result),
                        channel=ChannelNode(channel_id=channel.channel_id),
                    )
                    if result:
                        logger.info(f"채널 식별자에 연결된 채널 ID를 MongoDB에 입력했습니다. post ID: {post_id}, path: {mongo_path}")
                    else:
                        logger.error(f"post ID 또는 mongoDB path가 잘못 입력되었습니다. post ID: {post_id}, path: {mongo_path}")

                response = requests.post(
                    url=urljoin(os.getenv("FASTAPI_HOST"), f"/api/v1/channel/{channel.channel_id}/monitor"),
                    timeout=10,
                )
                logger.info(f"FastAPI 서버에 채널 모니터링을 요청했습니다. "
                            f"status code: {response.status_code}, response: {response.text}")

                # 채널 메시지 전체 수집 및 저장
                logger.info(f"채널 메시지 수집을 시도합니다: {channel_identifier}")
                channel_entity = await client.get_channel(channel_identifier, ChannelHandler())
                async for _ in client.iter_messages(channel_entity, MessageHandler()):
                    pass
                logger.info(f"채널 내의 모든 메세지를 수집하고 DB에 저장했습니다: {channel_identifier}")

                if post_id and mongo_path:
                    result = post_collection.update_one(
                        {"_id": post_id},
                        {"$set": {mongo_path+".is_processed": True}}
                    )
                    if result.modified_count == 1:
                        logger.info(f"텔레그램 식별자의 처리 여부를 완료로 변경했습니다. post ID: {post_id}, path: {mongo_path}")
                    elif result.matched_count == 0:
                        logger.error(f"post ID 또는 mongoDB path가 잘못 입력되었습니다. post ID: {post_id}, path: {mongo_path}")
                    else:
                        logger.error(f"텔레그램 식별자의 처리 여부가 반영되지 않았습니다. post ID: {post_id}, path: {mongo_path}")

        except Exception as e:
            if type(e) in ACCEPTABLE_EXCEPTIONS: # 예상되는 에러
                logger.warning(f"예상된 오류 발생: {type(e).__name__}: {str(e)}")

                if post_id and mongo_path:
                    result = post_collection.update_one(
                        {"_id": post_id},
                        {"$set": {
                            mongo_path+".is_processed": True,
                            mongo_path+".error": f"{type(e).__name__}: {str(e)}"
                        }}
                    )
                    if result.modified_count == 1:
                        logger.info(f"텔레그램 식별자의 처리 여부를 완료로 변경하고 발생한 오류를 기록했습니다. "
                                    f"post ID: {post_id}, path: {mongo_path}")
                    elif result.matched_count == 0:
                        logger.error(f"post ID 또는 mongoDB path가 잘못 입력되었습니다. post ID: {post_id}, path: {mongo_path}")
                    else:
                        logger.error(f"텔레그램 식별자의 처리 여부가 반영되지 않았습니다. post ID: {post_id}, path: {mongo_path}")
            else:
                logger.error(f"예상하지 못한 오류 발생: {type(e).__name__}: {str(e)}")
                raise e # 예상하지 못한 에러

    asyncio.run(_run())