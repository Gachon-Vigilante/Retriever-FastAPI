"""텔레그램 클라이언트 인증 API 모듈 - WebSocket 기반 대화형 인증

이 모듈은 Telethon 클라이언트의 텔레그램 인증 과정을 WebSocket을 통해 처리하는
API 엔드포인트를 제공합니다. 인증 과정에서 필요한 사용자 입력(전화번호, 인증 코드 등)을
WebSocket을 통해 실시간으로 주고받으며, 스레드 안전한 입력 리다이렉션을 구현합니다.

Telegram Client Authentication API Module - Interactive authentication via WebSocket

This module provides API endpoints for processing Telegram authentication of Telethon clients
through WebSocket. It handles user inputs required during authentication (phone numbers, verification codes, etc.)
in real-time through WebSocket and implements thread-safe input redirection.
"""

import builtins
import asyncio
import threading
from queue import Queue, Empty
from contextlib import contextmanager
from fastapi import WebSocket, APIRouter
from telethon import TelegramClient
from telethon.sessions import StringSession

from routes.teleprobe.register import register, RegisterResponse
from teleprobe.models import TelegramCredentials
from utils import Logger

logger = Logger(__name__)


router = APIRouter(prefix="/auth")


class ThreadSafeInputRedirector:
    """스레드 안전한 입력 리다이렉션을 제공하는 클래스

    Telethon 클라이언트의 인증 과정에서 발생하는 input() 호출을 WebSocket을 통해
    처리할 수 있도록 리다이렉션하는 기능을 제공합니다. 멀티스레드 환경에서
    안전하게 작동하며, 스레드별로 독립적인 리다이렉션 상태를 관리합니다.

    Class providing thread-safe input redirection

    Provides functionality to redirect input() calls that occur during Telethon client
    authentication process to be handled through WebSocket. Works safely in multi-threaded
    environments and manages independent redirection states for each thread.

    Attributes:
        response_queue (Queue): FastAPI에서 Telethon으로 사용자 입력을 전달하는 동기 큐
                              Synchronous queue for passing user input from FastAPI to Telethon
        original_input (callable): 원본 builtins.input 함수의 참조
                                  Reference to original builtins.input function
        local (threading.local): 스레드별 독립 저장소 (리다이렉션 상태 관리)
                               Thread-local storage (manages redirection state)
        prompt_async_queue (asyncio.Queue): Telethon에서 FastAPI로 프롬프트를 전달하는 비동기 큐
                                          Asynchronous queue for passing prompts from Telethon to FastAPI

    Examples:
        redirector = ThreadSafeInputRedirector()
        redirector.set_async_queue(async_queue)

        with redirector.redirect_for_current_thread():
            # 이 컨텍스트에서 input() 호출은 WebSocket으로 리다이렉션됨
            user_input = input("전화번호를 입력하세요: ")

    Note:
        이 클래스는 Telethon의 인증 과정에서만 사용되며, 일반적인 용도로는
        권장되지 않습니다. 스레드 안전성을 위해 복잡한 로직을 포함합니다.

        This class is intended only for Telethon's authentication process and
        is not recommended for general use. Contains complex logic for thread safety.
    """

    def __init__(self):
        """ThreadSafeInputRedirector 인스턴스를 초기화합니다.

        필요한 큐와 스레드별 저장소를 초기화하고, 원본 input 함수의 참조를 저장합니다.

        Initialize ThreadSafeInputRedirector instance.

        Initializes required queues and thread-local storage, and stores reference to original input function.
        """
        self.response_queue = Queue()  # FastAPI → Telethon (동기 Queue)
        self.original_input = builtins.input
        self.local = threading.local()  # 스레드별 저장소
        self.prompt_async_queue = None  # Telethon → FastAPI 비동기 Queue (나중에 설정)

    def set_async_queue(self, async_queue):
        """비동기 큐를 설정하는 메서드 (FastAPI 스레드에서 호출)

        Telethon에서 FastAPI로 프롬프트를 전달하기 위한 비동기 큐를 설정합니다.

        Method to set asynchronous queue (called from FastAPI thread)

        Sets asynchronous queue for passing prompts from Telethon to FastAPI.

        Args:
            async_queue (asyncio.Queue): 설정할 비동기 큐
                                       Asynchronous queue to set
        """
        self.prompt_async_queue = async_queue

    def custom_input(self, prompt_text=""):
        """커스텀 input 함수 - builtins.input을 대체하는 함수

        현재 스레드에서 리다이렉션이 활성화된 경우 WebSocket을 통해 입력을 받고,
        비활성화된 경우 원본 input 함수를 사용합니다.

        Custom input function - Function to replace builtins.input

        Uses WebSocket for input if redirection is active in current thread,
        otherwise uses original input function.

        Args:
            prompt_text (str): 사용자에게 표시할 프롬프트 텍스트
                             Prompt text to display to user

        Returns:
            str: 사용자가 입력한 문자열
                String entered by user

        Note:
            최대 5분(300초) 동안 사용자 입력을 대기합니다.
            Waits for user input for up to 5 minutes (300 seconds).
        """
        # 현재 스레드에 리다이렉터가 활성화되어 있는지 확인
        if not getattr(self.local, 'is_redirected', False):
            # 이 스레드에서는 리다이렉션이 비활성화됨 - 원래 input 사용
            logger.debug(f"Thread {threading.current_thread().name} using original input")
            return self.original_input(prompt_text)

        # 현재 스레드에서 리다이렉션 활성화됨
        logger.debug(f"Thread {threading.current_thread().name} sending prompt: {prompt_text}")

        # 비동기 Queue에 프롬프트 추가 (스레드 안전)
        if self.prompt_async_queue:
            self.prompt_async_queue.put_nowait(prompt_text)
        else:
            logger.error("Async queue not set! Falling back to original input.")
            return self.original_input(prompt_text)

        # 응답 대기 (블로킹, 최대 5분)
        try:
            result = self.response_queue.get(timeout=300)
            logger.debug(f"Got input response: {result[:3]}{'*' * max(0, len(result) - 3)}")
            return result
        except Exception as err:
            logger.error(f"Exception in custom_input: {err}")
            return ""

    @contextmanager
    def redirect_for_current_thread(self):
        """현재 스레드에서만 안전한 input 리다이렉션을 제공하는 컨텍스트 매니저

        현재 스레드에서만 input 함수를 WebSocket으로 리다이렉션하고,
        컨텍스트가 종료되면 원상 복구합니다. 다른 스레드에는 영향을 주지 않습니다.

        Context manager providing safe input redirection for current thread only

        Redirects input function to WebSocket only in current thread and
        restores original state when context ends. Does not affect other threads.

        Yields:
            ThreadSafeInputRedirector: 설정된 리다이렉터 인스턴스
                                     Configured redirector instance

        Examples:
            with redirector.redirect_for_current_thread():
                # 이 블록 내에서 input() 호출은 WebSocket으로 처리됨
                phone = input("Enter phone number: ")

        Note:
            전역 builtins.input은 한 번만 교체되며, 스레드별 상태로 리다이렉션을 제어합니다.
            Global builtins.input is replaced only once, with redirection controlled by thread-local state.
        """
        thread_name = threading.current_thread().name
        logger.info(f"Activating input redirection for thread: {thread_name}")

        # builtins.input을 한 번만 교체 (전역적으로)
        if builtins.input != self.custom_input:
            builtins.input = self.custom_input
            logger.debug("Global input function replaced")

        # 현재 스레드에서만 리다이렉션 활성화
        self.local.is_redirected = True

        try:
            yield self
        except Exception as e:
            logger.error(f"Exception during input redirection in thread {thread_name}: {e}")
            raise
        finally:
            # 현재 스레드의 리다이렉션만 비활성화
            self.local.is_redirected = False
            logger.info(f"Input redirection deactivated for thread: {thread_name}")

            # Note: builtins.input은 복구하지 않음 (다른 스레드가 사용 중일 수 있음)
            # 대신 custom_input에서 스레드별로 확인하여 처리


@router.websocket("")
async def telethon_auth_callback(websocket: WebSocket):
    """텔레그램 클라이언트 인증을 위한 WebSocket 엔드포인트

    클라이언트로부터 텔레그램 API 자격증명을 받아 Telethon 클라이언트를 생성하고
    인증 과정을 진행합니다. 인증 중 필요한 사용자 입력(전화번호, 인증 코드 등)을
    WebSocket을 통해 실시간으로 주고받으며, 성공 시 액세스 토큰을 반환합니다.

    WebSocket endpoint for Telegram client authentication

    Receives Telegram API credentials from client, creates Telethon client and
    proceeds with authentication process. Exchanges required user inputs 
    (phone numbers, verification codes, etc.) in real-time through WebSocket
    during authentication, and returns access token upon success.

    Args:
        websocket (WebSocket): FastAPI WebSocket 연결 객체
                              FastAPI WebSocket connection object

    WebSocket Protocol:
        Initial Request:
            {
                "api_id": int,     # Telegram API ID
                "api_hash": str    # Telegram API Hash
            }

        Prompt Messages (서버 → 클라이언트):
            {
                "type": "input_request",
                "prompt": str      # 입력 요청 메시지
            }

        Input Response (클라이언트 → 서버):
            {
                "input": str       # 사용자 입력값
            }

        Success Response:
            {
                "type": "success",
                "session_string": str  # 등록 응답 JSON
            }

        Error Response:
            {
                "type": "error",
                "message": str     # 오류 메시지
            }

    Raises:
        WebSocketException: WebSocket 연결 오류 시
                          On WebSocket connection errors
        Exception: 인증 과정 중 발생하는 모든 예외
                  All exceptions during authentication process

    Examples:
        # JavaScript 클라이언트 예시
        const ws = new WebSocket('ws://localhost:8000/teleprobe/auth');

        ws.onopen = function() {
            ws.send(JSON.stringify({
                api_id: 12345,
                api_hash: "abcdef1234567890"
            }));
        };

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'input_request') {
                const userInput = prompt(data.prompt);
                ws.send(JSON.stringify({input: userInput}));
            }
        };

    Note:
        인증 과정:
        1. 클라이언트에서 API 자격증명 전송
        2. Telethon 클라이언트 생성 및 별도 스레드에서 실행
        3. 인증 중 필요한 입력을 WebSocket으로 요청
        4. 사용자 입력을 받아 Telethon으로 전달
        5. 인증 완료 시 세션 문자열로 토큰 등록
        6. 액세스 토큰 반환

        Authentication process:
        1. Client sends API credentials
        2. Create Telethon client and run in separate thread
        3. Request required inputs through WebSocket during auth
        4. Receive user inputs and forward to Telethon
        5. Register token with session string upon auth completion
        6. Return access token
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    redirector = ThreadSafeInputRedirector()

    # 비동기 Queue 생성 및 설정 (비동기 함수에서 설정하지 않거나 Event 방식을 사용하면 builtins.input이 제대로 대체되지 않음)
    prompt_async_queue = asyncio.Queue()
    redirector.set_async_queue(prompt_async_queue)

    try:
        init_data = await websocket.receive_json()
        api_id = init_data["api_id"]
        api_hash = init_data["api_hash"]

        logger.info(f"Starting Telethon auth for API ID: {api_id}")

        # Telethon 실행용 스레드
        telethon_result = Queue()

        def telethon_worker():
            try:
                logger.debug(
                    f"Creating new event loop in worker thread: {threading.current_thread().name}")
                # 새로운 이벤트 루프 생성
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def start_auth() -> RegisterResponse:
                    # 현재 스레드에서만, 안전한 input 리다이렉션 사용
                    with redirector.redirect_for_current_thread():
                        logger.info("Starting Telethon client within redirect context")
                        async with TelegramClient(StringSession(), api_id, api_hash) as client:
                            logger.info("Telethon client created, starting authentication...")
                            await client.start()
                            logger.info("Telethon client started successfully")
                            session_string = client.session.save()
                            logger.debug(f"Session string generated (length: {len(session_string)})")
                            register_response = await register(
                                TelegramCredentials(
                                    api_id=api_id,
                                    api_hash=api_hash,
                                    session_string=session_string
                                )
                            )
                            return register_response

                result = loop.run_until_complete(start_auth())
                loop.close()
                logger.debug("Event loop closed in worker thread")
                telethon_result.put(("success", result.model_dump_json()))

            except Exception as err:
                logger.error(f"Telethon worker error: {str(err)}")
                telethon_result.put(("error", str(err)))

        # Telethon 스레드 시작
        logger.debug("Starting Telethon worker thread")
        telethon_thread = threading.Thread(target=telethon_worker, daemon=True, name="TelethonWorker")
        telethon_thread.start()

        async def handle_websocket_messages():
            """WebSocket 메시지만 처리하는 전용 태스크"""
            logger.debug("Starting WebSocket message handler")
            while telethon_thread.is_alive():
                try:
                    response = await websocket.receive_json()
                    if "input" in response:
                        user_input = response.get("input", "")
                        logger.info(
                            f"Received input from client: {user_input[:3]}{'*' * max(0, len(user_input) - 3)}")
                        redirector.response_queue.put(user_input)
                        logger.debug("User input forwarded to Telethon thread")
                except Exception as e:
                    logger.error(f"WebSocket receive error: {e}")
                    break

        async def handle_prompts():
            """프롬프트만 처리하는 전용 태스크 - 완전한 이벤트 기반"""
            logger.debug("Starting prompt handler")
            while telethon_thread.is_alive():
                try:
                    # 완전한 이벤트 기반 - 프롬프트가 올 때까지 대기 (CPU 사용 없음)
                    prompt = await asyncio.wait_for(
                        prompt_async_queue.get(),
                        timeout=1.0  # 1초마다 스레드 상태만 확인
                    )

                    logger.info(f"Sending prompt to client: {prompt}")
                    await websocket.send_json({
                        "type": "input_request",
                        "prompt": prompt
                    })

                except asyncio.TimeoutError:
                    # 타임아웃 - 스레드 상태 재확인을 위해 계속 (프롬프트 확인 안함)
                    continue
                except Exception as e:
                    logger.error(f"Prompt handling error: {e}")
                    break

        # 두 태스크를 동시 실행
        logger.debug("Starting event-based message processing")
        websocket_task = asyncio.create_task(handle_websocket_messages())
        prompt_task = asyncio.create_task(handle_prompts())

        try:
            # Telethon 스레드 완료까지 대기 (비동기적으로)
            logger.debug("Waiting for Telethon thread to complete")
            await asyncio.to_thread(lambda: telethon_thread.join(timeout=600))  # 10분 타임아웃
        finally:
            # 태스크 정리
            logger.debug("Cleaning up async tasks")
            websocket_task.cancel()
            prompt_task.cancel()

            # 태스크 완료 대기
            try:
                await asyncio.gather(websocket_task, prompt_task, return_exceptions=True)
            except Exception:
                pass

        if telethon_thread.is_alive():
            logger.warning("Telethon thread did not complete within timeout")

        # 결과 확인
        try:
            result_type, result_value = telethon_result.get(timeout=1)
            if result_type == "success":
                logger.info("Authentication successful")
                await websocket.send_json({
                    "type": "success",
                    "session_string": result_value
                })
            else:
                logger.error(f"Authentication failed with error: {result_value}")
                raise Exception(result_value)

        except Empty:
            logger.error("Telethon authentication timed out")
            raise Exception("Telethon authentication timed out")

    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        logger.info("WebSocket connection cleanup completed")