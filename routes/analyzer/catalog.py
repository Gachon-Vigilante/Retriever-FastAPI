from fastapi import APIRouter

from genai.analyzers.channel import update_all_catalogs

router = APIRouter(prefix="/catalog")

@router.patch("/all")
async def register_batch():
    await update_all_catalogs()
    return {"message": "all catalogs updated."}