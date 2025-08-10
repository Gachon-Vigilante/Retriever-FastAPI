from fastapi import APIRouter

import core.sqlite
from . import (
    auth,
    channel,
    message
)

router = APIRouter(prefix="/teleprobe")

router.include_router(auth.router)
router.include_router(channel.router)
router.include_router(message.router)