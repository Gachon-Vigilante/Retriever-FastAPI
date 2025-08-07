from typing import TYPE_CHECKING, Optional, Union

from fastapi import APIRouter

from teleprobe.models import ChannelInfo
from utils import logger

if TYPE_CHECKING:
    from teleprobe.base import TeleprobeClient


router = APIRouter(prefix="/channel")


class ChannelMethods:
    async def get_channel_info(
            self:'TeleprobeClient',
            channel_key: Union[int, str],
    ) -> Optional[ChannelInfo]:
        """채널 정보를 비동기적으로 가져옵니다.
        
        이 메서드는 비동기 방식으로 작동하므로 await로 호출해야 합니다.
        
        Args:
            channel_key: 채널 ID, 사용자명 또는 초대 링크
            
        Returns:
            ChannelInfo 객체 또는 연결 실패시 None
        """
        if not await self._ensure_connected():
            return None

        connection_result = await self.connect_channel(channel_key)
        if not connection_result.success:
            logger.warning("[Channel] 채널 정보를 받아올 수 없습니다. 채널 연결에 실패했습니다.")
            return None

        entity = connection_result.entity

        return ChannelInfo(
            id=entity.id,
            title=entity.title,
            username=entity.username,
            restricted=entity.restricted, # 채널에 제한이 있는지 여부 (boolean)
            started_at=entity.date, # 채널이 생성된 일시 (datetime.datetime)
        )