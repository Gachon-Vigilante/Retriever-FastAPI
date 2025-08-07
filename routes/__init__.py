from fastapi import APIRouter

from . import teleprobe

root_router = APIRouter(prefix="")

root_router.include_router(teleprobe.router)