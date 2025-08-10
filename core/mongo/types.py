"""MongoDB 컬렉션에서 사용되는 타입 정의 모듈 - 열거형 타입들

이 모듈은 MongoDB 문서 모델에서 사용되는 다양한 열거형 타입들을 정의합니다.
메시지 발신자 타입, 채널 상태 등 고정된 값 집합을 가지는 필드들을 위한
타입 안전성을 제공합니다.

MongoDB Collection Type Definitions Module - Enumeration types

This module defines various enumeration types used in MongoDB document models.
It provides type safety for fields with fixed value sets such as
message sender types, channel statuses, etc.
"""

from enum import Enum, StrEnum


class SenderType(StrEnum):
    """텔레그램 메시지 발신자 타입을 나타내는 문자열 열거형

    텔레그램에서 메시지를 보낼 수 있는 엔티티의 타입을 구분합니다.
    사용자 계정과 채널을 구분하여 메시지의 출처를 명확하게 분류할 수 있습니다.

    String enumeration representing Telegram message sender types

    Distinguishes the types of entities that can send messages in Telegram.
    Separates user accounts and channels to clearly classify message sources.

    Attributes:
        USER (str): 개인 사용자 계정에서 전송된 메시지
                   Message sent from a personal user account
        CHANNEL (str): 채널에서 전송된 메시지
                      Message sent from a channel

    Examples:
        # 사용자가 보낸 메시지 처리
        if sender_type == SenderType.USER:
            process_user_message()

        # 채널에서 온 메시지 처리
        if sender_type == SenderType.CHANNEL:
            process_channel_message()
    """
    USER = "user"
    CHANNEL = "channel"


class ChannelStatus(str, Enum):
    """텔레그램 채널의 상태를 나타내는 문자열 열거형

    채널의 현재 접근 가능성과 제한 상태를 분류합니다.
    채널 모니터링과 상태 관리를 위해 사용되며, 접근 권한과 제한 사항을 구분합니다.

    String enumeration representing Telegram channel status

    Classifies the current accessibility and restriction status of channels.
    Used for channel monitoring and status management, distinguishing
    access permissions and restrictions.

    Attributes:
        ACTIVE (str): 정상적으로 접근 가능한 활성 채널
                     Active channel that is normally accessible
        INACTIVE (str): 비활성화된 채널 (일시적 또는 영구적)
                       Inactive channel (temporary or permanent)
        RESTRICTED (str): 접근이 제한된 채널 (지역, 연령 제한 등)
                         Restricted channel (regional, age restrictions, etc.)
        BANNED (str): 차단되거나 삭제된 채널
                     Banned or deleted channel

    Examples:
        # 활성 채널만 모니터링
        if channel.status == ChannelStatus.ACTIVE:
            monitor_channel(channel)

        # 제한된 채널 처리
        if channel.status == ChannelStatus.RESTRICTED:
            handle_restricted_channel(channel)
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESTRICTED = "restricted"
    BANNED = "banned"
