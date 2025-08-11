from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from handlers import MessageHandler
from routes.responses import SuccessfulResponse, TeleprobeHTTPException
from routes.teleprobe.models import channelKeyPath, TeleprobeClientManager
from teleprobe.base import TeleprobeClient
from utils import Logger

logger = Logger(__name__)

router = APIRouter(prefix="/channel")

@router.post("/{channel_key}/messages")
async def post_messages_from_channel(
        client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
        channel_key: channelKeyPath,
):
    """
    Handles the POST request to process and store messages from a Telegram channel.

    This asynchronous function retrieves channel information, iterates through messages
    from the specified Telegram channel, processes them, and stores them.

    Args:
        client: The TeleprobeClient instance provided by the dependency manager, used
            to interact with the Telegram client.
        channel_key: The unique identifier for the target Telegram channel from which
            messages are to be retrieved.

    Raises:
        HTTPException: If the channel is not found (404), the channel key has an invalid
            format (400), the Telegram service is unavailable (503), or any internal
            server error occurs (500).

    Returns:
        A dictionary containing a success message if all messages are successfully stored.
    """
    try:
        async with client:
            # 채널 정보 조회 (비동기 방식)
            logger.info(f"채널 정보 조회 요청: {channel_key}")
            channel_entity = await client.get_channel(channel_key)

            if not channel_entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"채널 정보를 찾을 수 없습니다: {channel_key}"
                )

            client.iter_messages(channel_entity, MessageHandler())
            logger.info("채널 내의 모든 메세지를 수집하고 DB에 저장했습니다.")
            return SuccessfulResponse(message=f"채널 내의 모든 메세지를 수집하고 DB에 저장했습니다. "
                                  f"Channel ID: {channel_entity.id}, Channel Type: {type(channel_entity)}")

    except Exception as e:
        TeleprobeHTTPException.from_error(e)