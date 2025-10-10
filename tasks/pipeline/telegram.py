from celery import shared_task

from utils import Logger

logger = Logger(__name__)


@shared_task(name=__name__)
def telegram_channel_task(channel_key: str):
    logger.info(f"Telegram channel key: {channel_key}")