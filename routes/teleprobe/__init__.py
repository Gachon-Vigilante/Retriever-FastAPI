from fastapi import APIRouter

import core.sqlite
from . import (
    auth,
    channel,
    register
)

router = APIRouter(prefix="/teleprobe")

router.include_router(auth.router)
router.include_router(channel.router)
router.include_router(core.sqlite.router)