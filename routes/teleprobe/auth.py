import builtins
import asyncio
import threading
from queue import Queue, Empty
from contextlib import contextmanager
from fastapi import WebSocket, APIRouter
from telethon import TelegramClient
from telethon.sessions import StringSession
from utils import logger


router = APIRouter(prefix="/auth")


class ThreadSafeInputRedirector:
    def __init__(self):
        self.response_queue = Queue()  # FastAPI → Telethon (동기 Queue)
        self.original_input = builtins.input
        self.local = threading.local()  # 스레드별 저장소
        self.prompt_async_queue = None  # Telethon → FastAPI 비동기 Queue (나중에 설정)

    def set_async_queue(self, async_queue):
        """비동기 Queue 설정 (FastAPI 스레드에서 호출)"""
        self.prompt_async_queue = async_queue

    def custom_input(self, prompt_text=""):
        # 현재 스레드에 리다이렉터가 활성화되어 있는지 확인
        if not getattr(self.local, 'is_redirected', False):
            # 이 스레드에서는 리다이렉션이 비활성화됨 - 원래 input 사용
            logger.debug(f"[TelegramAuth] Thread {threading.current_thread().name} using original input")
            return self.original_input(prompt_text)

        # 현재 스레드에서 리다이렉션 활성화됨
        logger.debug(f"[TelegramAuth] Thread {threading.current_thread().name} sending prompt: {prompt_text}")

        # 비동기 Queue에 프롬프트 추가 (스레드 안전)
        if self.prompt_async_queue:
            self.prompt_async_queue.put_nowait(prompt_text)
        else:
            logger.error("[TelegramAuth] Async queue not set! Falling back to original input.")
            return self.original_input(prompt_text)

        # 응답 대기 (블로킹, 최대 5분)
        try:
            result = self.response_queue.get(timeout=300)
            logger.debug(f"[TelegramAuth] Got input response: {result[:3]}{'*' * max(0, len(result) - 3)}")
            return result
        except Exception as err:
            logger.error(f"[TelegramAuth] Exception in custom_input: {err}")
            return ""

    @contextmanager
    def redirect_for_current_thread(self):
        """현재 스레드에서만 안전한 input 리다이렉션"""
        thread_name = threading.current_thread().name
        logger.info(f"[TelegramAuth] Activating input redirection for thread: {thread_name}")

        # builtins.input을 한 번만 교체 (전역적으로)
        if builtins.input != self.custom_input:
            builtins.input = self.custom_input
            logger.debug("[TelegramAuth] Global input function replaced")

        # 현재 스레드에서만 리다이렉션 활성화
        self.local.is_redirected = True

        try:
            yield self
        except Exception as e:
            logger.error(f"[TelegramAuth] Exception during input redirection in thread {thread_name}: {e}")
            raise
        finally:
            # 현재 스레드의 리다이렉션만 비활성화
            self.local.is_redirected = False
            logger.info(f"[TelegramAuth] Input redirection deactivated for thread: {thread_name}")

            # Note: builtins.input은 복구하지 않음 (다른 스레드가 사용 중일 수 있음)
            # 대신 custom_input에서 스레드별로 확인하여 처리


@router.websocket("")
async def telethon_auth_callback(websocket: WebSocket):
    await websocket.accept()
    logger.info("[TelegramAuth] WebSocket connection accepted")

    redirector = ThreadSafeInputRedirector()

    # 비동기 Queue 생성 및 설정 (비동기 함수에서 설정하지 않거나 Event 방식을 사용하면 builtins.input이 제대로 대체되지 않음)
    prompt_async_queue = asyncio.Queue()
    redirector.set_async_queue(prompt_async_queue)

    try:
        init_data = await websocket.receive_json()
        api_id = init_data["api_id"]
        api_hash = init_data["api_hash"]

        logger.info(f"[TelegramAuth] Starting Telethon auth for API ID: {api_id}")

        # Telethon 실행용 스레드
        telethon_result = Queue()

        def telethon_worker():
            try:
                logger.debug(
                    f"[TelegramAuth] Creating new event loop in worker thread: {threading.current_thread().name}")
                # 새로운 이벤트 루프 생성
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def start_auth():
                    # 현재 스레드에서만, 안전한 input 리다이렉션 사용
                    with redirector.redirect_for_current_thread():
                        logger.info("[TelegramAuth] Starting Telethon client within redirect context")
                        async with TelegramClient(StringSession(), api_id, api_hash) as client:
                            logger.info("[TelegramAuth] Telethon client created, starting authentication...")
                            await client.start()
                            logger.info("[TelegramAuth] Telethon client started successfully")
                            session_string = client.session.save()
                            logger.debug(f"[TelegramAuth] Session string generated (length: {len(session_string)})")
                            return session_string

                result = loop.run_until_complete(start_auth())
                loop.close()
                logger.debug("[TelegramAuth] Event loop closed in worker thread")
                telethon_result.put(("success", result))

            except Exception as err:
                logger.error(f"[TelegramAuth] Telethon worker error: {str(err)}")
                telethon_result.put(("error", str(err)))

        # Telethon 스레드 시작
        logger.debug("[TelegramAuth] Starting Telethon worker thread")
        telethon_thread = threading.Thread(target=telethon_worker, daemon=True, name="TelethonWorker")
        telethon_thread.start()

        async def handle_websocket_messages():
            """WebSocket 메시지만 처리하는 전용 태스크"""
            logger.debug("[TelegramAuth] Starting WebSocket message handler")
            while telethon_thread.is_alive():
                try:
                    response = await websocket.receive_json()
                    if "input" in response:
                        user_input = response.get("input", "")
                        logger.info(
                            f"[TelegramAuth] Received input from client: {user_input[:3]}{'*' * max(0, len(user_input) - 3)}")
                        redirector.response_queue.put(user_input)
                        logger.debug("[TelegramAuth] User input forwarded to Telethon thread")
                except Exception as e:
                    logger.error(f"[TelegramAuth] WebSocket receive error: {e}")
                    break

        async def handle_prompts():
            """프롬프트만 처리하는 전용 태스크 - 완전한 이벤트 기반"""
            logger.debug("[TelegramAuth] Starting prompt handler")
            while telethon_thread.is_alive():
                try:
                    # 완전한 이벤트 기반 - 프롬프트가 올 때까지 대기 (CPU 사용 없음)
                    prompt = await asyncio.wait_for(
                        prompt_async_queue.get(),
                        timeout=1.0  # 1초마다 스레드 상태만 확인
                    )

                    logger.info(f"[TelegramAuth] Sending prompt to client: {prompt}")
                    await websocket.send_json({
                        "type": "input_request",
                        "prompt": prompt
                    })

                except asyncio.TimeoutError:
                    # 타임아웃 - 스레드 상태 재확인을 위해 계속 (프롬프트 확인 안함)
                    continue
                except Exception as e:
                    logger.error(f"[TelegramAuth] Prompt handling error: {e}")
                    break

        # 두 태스크를 동시 실행
        logger.debug("[TelegramAuth] Starting event-based message processing")
        websocket_task = asyncio.create_task(handle_websocket_messages())
        prompt_task = asyncio.create_task(handle_prompts())

        try:
            # Telethon 스레드 완료까지 대기 (비동기적으로)
            logger.debug("[TelegramAuth] Waiting for Telethon thread to complete")
            await asyncio.to_thread(lambda: telethon_thread.join(timeout=600))  # 10분 타임아웃
        finally:
            # 태스크 정리
            logger.debug("[TelegramAuth] Cleaning up async tasks")
            websocket_task.cancel()
            prompt_task.cancel()

            # 태스크 완료 대기
            try:
                await asyncio.gather(websocket_task, prompt_task, return_exceptions=True)
            except Exception:
                pass

        if telethon_thread.is_alive():
            logger.warning("[TelegramAuth] Telethon thread did not complete within timeout")

        # 결과 확인
        try:
            result_type, result_value = telethon_result.get(timeout=1)
            if result_type == "success":
                logger.info("[TelegramAuth] Authentication successful")
                await websocket.send_json({
                    "type": "success",
                    "session_string": result_value
                })
            else:
                logger.error(f"[TelegramAuth] Authentication failed with error: {result_value}")
                raise Exception(result_value)

        except Empty:
            logger.error("[TelegramAuth] Telethon authentication timed out")
            raise Exception("Telethon authentication timed out")

    except Exception as e:
        logger.error(f"[TelegramAuth] Authentication failed: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        logger.info("[TelegramAuth] WebSocket connection cleanup completed")