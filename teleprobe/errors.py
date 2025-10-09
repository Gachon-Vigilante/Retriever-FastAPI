"""Teleprobe 예외 처리 모듈 - 커스텀 예외 클래스들과 Telethon 예외 재사용

이 모듈은 Teleprobe 시스템에서 발생할 수 있는 다양한 예외 상황을 처리하기 위한
커스텀 예외 클래스들을 정의합니다. Telethon의 기존 예외들을 재사용하고,
Teleprobe 특화 예외들을 추가로 정의하여 명확한 에러 처리를 제공합니다.

Teleprobe Exception Handling Module - Custom exception classes and Telethon exception reuse

This module defines custom exception classes for handling various exception scenarios
that can occur in the Teleprobe system. It reuses existing Telethon exceptions and
additionally defines Teleprobe-specific exceptions to provide clear error handling.
"""

from typing import Optional
from telethon.errors import (
    ApiIdInvalidError as TelethonApiIdInvalidError,
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    UsernameInvalidError,
)

__all__ = [
    'InviteHashEmptyError',
    'InviteHashExpiredError',
    'InviteHashInvalidError',
    'ChannelInvalidError',
    'ChannelPrivateError',
    'FloodWaitError',
    'UsernameInvalidError',
    'ApiIdInvalidError',
    'ApiHashInvalidError',
    'UnknownInvitationTypeError',
    'SessionStringInvalidError',
    'ChannelNotFoundError',
    'EntityNotFoundError',
    'UsernameNotFoundError',
    'ChannelKeyInvalidError',
    'ChannelNotWatchedError',
    'ChannelAlreadyWatchedError',
    'NotChannelError',
    'ACCEPTABLE_EXCEPTIONS',
]


class ApiIdInvalidError(TelethonApiIdInvalidError):
    """잘못된 Telegram API ID에 대한 예외 클래스

    텔레그램 개발자 포털에서 발급받은 API ID가 유효하지 않거나 잘못된 경우 발생합니다.
    Telethon의 ApiIdInvalidError를 상속받아 추가 메시지 필드를 제공합니다.

    Exception class for invalid Telegram API ID

    Raised when API ID issued from Telegram developer portal is invalid or incorrect.
    Inherits from Telethon's ApiIdInvalidError and provides additional msg field.

    Examples:
        raise ApiIdInvalidError("제공된 API ID가 올바르지 않습니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "API ID is invalid.")

class ApiHashInvalidError(Exception):
    """잘못된 Telegram API Hash에 대한 예외 클래스

    텔레그램 개발자 포털에서 발급받은 API Hash가 유효하지 않거나 잘못된 경우 발생합니다.
    32자리 16진수 문자열이 아니거나 형식에 맞지 않는 경우에 사용됩니다.

    Exception class for invalid Telegram API Hash

    Raised when API Hash issued from Telegram developer portal is invalid or incorrect.
    Used when it's not a 32-character hexadecimal string or doesn't match required format.

    Examples:
        raise ApiHashInvalidError("API Hash는 32자리 16진수 문자열이어야 합니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "API Hash is invalid.")

class UnknownInvitationTypeError(Exception):
    """알 수 없는 초대 타입에 대한 예외 클래스

    텔레그램 초대 링크 처리 중 예상하지 못한 초대 정보 타입이 반환된 경우 발생합니다.
    ChatInvite, ChatInviteAlready 외의 알 수 없는 타입을 받았을 때 사용됩니다.

    Exception class for unknown invitation type

    Raised when unexpected invitation information type is returned during Telegram invite link processing.
    Used when receiving unknown types other than ChatInvite or ChatInviteAlready.

    Examples:
        raise UnknownInvitationTypeError(f"알 수 없는 초대 타입: {type(invite_info)}")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unknown invitation type.")

class SessionStringInvalidError(Exception):
    """잘못된 세션 문자열에 대한 예외 클래스

    Telethon 클라이언트의 세션 문자열이 유효하지 않거나 손상된 경우 발생합니다.
    세션 문자열 형식이 올바르지 않거나 디코딩할 수 없는 경우에 사용됩니다.

    Exception class for invalid session string

    Raised when Telethon client's session string is invalid or corrupted.
    Used when session string format is incorrect or cannot be decoded.

    Examples:
        raise SessionStringInvalidError("세션 문자열이 손상되었습니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Session string is invalid.")

class ChannelNotFoundError(Exception):
    """채널을 찾을 수 없는 경우에 대한 예외 클래스

    지정된 채널 ID나 사용자명으로 채널을 찾을 수 없는 경우 발생합니다.
    채널이 존재하지 않거나 접근 권한이 없는 경우에 사용됩니다.

    Exception class for channel not found

    Raised when channel cannot be found with specified channel ID or username.
    Used when channel doesn't exist or access permission is denied.

    Examples:
        raise ChannelNotFoundError("채널을 찾을 수 없습니다: @channelname")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Channel not found.")

class UsernameNotFoundError(Exception):
    """사용자명을 찾을 수 없는 경우에 대한 예외 클래스

    지정된 @username으로 사용자나 채널을 찾을 수 없는 경우 발생합니다.

    Exception class for username not found

    Raised when user or channel cannot be found with specified @username.
    Used when username doesn't exist or account is private.

    Examples:
        raise UsernameNotFoundError("사용자명을 찾을 수 없습니다: @username")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Username not found.")

class EntityNotFoundError(Exception):
    """어떠한 엔티티도 찾을 수 없는 경우에 대한 예외 클래스

    지정된 채널 식별자(@username, id 등)으로 사용자나 채널을 찾을 수 없는 경우 발생합니다.

    Examples:
        raise UsernameNotFoundError("사용자명을 찾을 수 없습니다: @username")
    """

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Entity not found.")

class ChannelKeyInvalidError(Exception):
    """잘못된 채널 키에 대한 예외 클래스

    채널을 식별하기 위한 키(채널 ID, 사용자명, 초대 링크)가 유효하지 않은 경우 발생합니다.
    지원되지 않는 형식이거나 올바르지 않은 값인 경우에 사용됩니다.

    Exception class for invalid channel key

    Raised when key for identifying channel (channel ID, username, invite link) is invalid.
    Used when format is not supported or value is incorrect.

    Examples:
        raise ChannelKeyInvalidError("지원되지 않는 채널 키 형식입니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Channel key is invalid.")

class ChannelNotWatchedError(Exception):
    """모니터링되지 않는 채널에 대한 예외 클래스

    모니터링을 중단하려는 채널이 현재 모니터링되고 있지 않은 경우 발생합니다.
    이벤트 핸들러가 등록되지 않은 채널의 모니터링을 중단하려 할 때 사용됩니다.

    Exception class for channel not being watched

    Raised when trying to stop monitoring a channel that is not currently being monitored.
    Used when attempting to stop monitoring channel with no registered event handler.

    Examples:
        raise ChannelNotWatchedError("이 채널은 현재 모니터링되지 않습니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Channel is not being watched.")

class ChannelAlreadyWatchedError(Exception):
    """이미 모니터링 중인 채널에 대한 예외 클래스

    이미 모니터링 중인 채널에 대해 추가로 모니터링을 시작하려는 경우 발생합니다.
    중복 모니터링을 방지하기 위해 사용됩니다.

    Exception class for channel already being watched

    Raised when trying to start monitoring a channel that is already being monitored.
    Used to prevent duplicate monitoring.

    Examples:
        raise ChannelAlreadyWatchedError("이 채널은 이미 모니터링 중입니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Channel is already being watched.")

class NotChannelError(Exception):
    """채널이 아닌 엔티티에 대한 예외 클래스

    채널 전용 작업을 수행하려 하지만 대상 엔티티가 채널이 아닌 경우 발생합니다.
    사용자, 그룹 등 채널이 아닌 엔티티에 채널 작업을 시도할 때 사용됩니다.

    Exception class for non-channel entity

    Raised when trying to perform channel-specific operations on non-channel entity.
    Used when attempting channel operations on users, groups, or other non-channel entities.

    Examples:
        raise NotChannelError("연결된 엔티티가 채널이 아닙니다.")
    """
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Connected entity is not a channel.")


ACCEPTABLE_EXCEPTIONS = (
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    UsernameInvalidError,
    ApiIdInvalidError,
    ApiHashInvalidError,
    UnknownInvitationTypeError,
    SessionStringInvalidError,
    ChannelNotFoundError,
    EntityNotFoundError,
    UsernameNotFoundError,
    ChannelKeyInvalidError,
    NotChannelError,
)