from fastapi import APIRouter
from .post import router as post_router
from .channel import router as channel_router

router = APIRouter(prefix="/clustering", tags=["clustering"])

router.include_router(post_router)
router.include_router(channel_router)
