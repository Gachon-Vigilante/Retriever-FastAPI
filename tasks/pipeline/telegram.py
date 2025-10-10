import asyncio
import os
from urllib.parse import urljoin

import requests
from bson import ObjectId
from celery import shared_task

from core.constants import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING
from core.mongo.connections import MongoCollections
from handlers import ChannelHandler, MessageHandler
from teleprobe import TeleprobeClient
from teleprobe.errors import ACCEPTABLE_EXCEPTIONS
from utils import Logger
from ..names import TELEGRAM_CHANNEL_TASK_NAME

logger = Logger(__name__)


@shared_task(name=TELEGRAM_CHANNEL_TASK_NAME)
def telegram_channel_task(channel_identifier: str, post_id: str | None = None, mongo_path: str | None = None):
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
                    result = post_collection.update_one(
                        {"_id": post_id},
                        {"$set": {mongo_path+".channel_id": channel.id}}
                    )
                    if result.modified_count == 1:
                        logger.info(f"채널 식별자에 연결된 채널 ID를 MongoDB에 입력했습니다. post ID: {post_id}, path: {mongo_path}")
                    elif result.matched_count == 0:
                        logger.error(f"post ID 또는 mongoDB path가 잘못 입력되었습니다. post ID: {post_id}, path: {mongo_path}")
                    else:
                        logger.error(f"채널 식별자에 연결된 채널 ID를 찾았지만 MongoDB에 저장할 수 없었습니다. post ID: {post_id}, path: {mongo_path}")

                response = requests.post(
                    url=urljoin(os.getenv("FASTAPI_HOST"), f"/api/v1/channel/{channel.id}/monitor"),
                    timeout=10,
                )
                logger.info(f"FastAPI 서버에 채널 모니터링을 요청했습니다. "
                            f"status code: {response.status_code}, response: {response.text}")

                # 채널 정보 조회 (비동기 방식)
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