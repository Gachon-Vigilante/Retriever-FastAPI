from fastapi import APIRouter

from . import auth, channel

router = APIRouter(prefix="/teleprobe")

router.include_router(auth.router)
router.include_router(channel.router)