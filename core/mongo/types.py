from enum import Enum, StrEnum


class SenderType(StrEnum):
    USER = "user"
    CHANNEL = "channel"


class ChannelStatus(str, Enum):
    """채널 상태 열거형"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESTRICTED = "restricted"
    BANNED = "banned"
