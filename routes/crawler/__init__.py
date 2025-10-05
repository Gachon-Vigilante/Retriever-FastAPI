from fastapi import APIRouter

from .start import router as start_router


router = APIRouter(prefix="/api/v1/crawling")

router.include_router(start_router)