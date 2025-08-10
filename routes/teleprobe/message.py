from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from telethon.tl.types import User as TelethonUser, Channel as TelethonChannel

from core.mongo.types import SenderType
from routes.teleprobe.models import channelKeyPath, TeleprobeClientManager
from teleprobe.base import TeleprobeClient
from core.mongo.schemas import Message
from utils import logger
from ..responses import SuccessfulResponse

router = APIRouter(prefix="/channel")

LOGGER_HEADER = "[ChannelMessages] "
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
        # 채널 정보 조회 (비동기 방식)
        logger.info(LOGGER_HEADER+f"채널 정보 조회 요청: {channel_key}")
        channel_entity = await client.get_channel(channel_key)

        if not channel_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"채널 정보를 찾을 수 없습니다: {channel_key}"
            )

        async for telethon_message in client.iter_messages(channel_entity):
            sender = await telethon_message.get_sender()
            if not sender:
                logger.error(LOGGER_HEADER+f"메세지 송신자를 받아올 수 없습니다.")
                sender_id = sender_type = None
            else:
                sender_id = sender.id
                if isinstance(sender, TelethonUser):
                    sender_type = SenderType.USER
                elif isinstance(sender, TelethonChannel):
                    sender_type = SenderType.CHANNEL
                else:
                    logger.warning(LOGGER_HEADER+f"메세지 송신자가 알려지지 않은 타입입니다. "
                                   f"Expected `User` or `Channel`, got `{type(sender)}`")
                    sender_type = None
            message: Message = Message.from_telethon(
                telethon_message,
                sender_id=sender_id,
                chat_id=channel_entity.id,
                sender_type=sender_type
            )
            message.store()
        logger.info(LOGGER_HEADER+"채널 내의 모든 메세지를 수집하고 DB에 저장했습니다.")
        return SuccessfulResponse(message=f"채널 내의 모든 메세지를 수집하고 DB에 저장했습니다. "
                                  f"Channel ID: {channel_entity.id}, Channel Type: {type(channel_entity)}")

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"잘못된 채널 키 형식 또는 채널 키가 없음: `{str(channel_key)}`"
        )
    except ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="텔레그램 서비스에 연결할 수 없습니다"
        )
    except Exception as e:
        logger.error(f"[ChannelMessages] 예상하지 못한 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 내부 오류가 발생했습니다"
        )