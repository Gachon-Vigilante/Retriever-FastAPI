from fastapi import APIRouter

from tasks.pipeline.poll_gemini import poll_gemini_batches_task
from utils import Logger
from .responses import SuccessfulResponse

logger = Logger(__name__)

polling_router = APIRouter(prefix="/api/v1/polling")


@polling_router.post("", response_model=SuccessfulResponse)
async def trigger_polling_task():
    """
    """
    poll_gemini_batches_task.delay()
    return SuccessfulResponse(message="Polling task is triggered.")
