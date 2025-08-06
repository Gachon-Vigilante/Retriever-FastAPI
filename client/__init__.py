from fastapi import APIRouter

from . import auth

router = APIRouter(prefix="/client")

router.include_router(auth.router)