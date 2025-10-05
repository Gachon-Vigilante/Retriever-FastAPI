from fastapi import APIRouter

from .batch import router as batch_router


router = APIRouter(prefix="/api/v1/analyzer")

router.include_router(batch_router)