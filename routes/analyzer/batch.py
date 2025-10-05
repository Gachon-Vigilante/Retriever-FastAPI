from fastapi import APIRouter

from genai.analyzers.post import PostAnalyzer, JobCompletionResult
from tasks.pipeline.analyze import analyze_batch_task

router = APIRouter(prefix="/batch")

@router.post("/register")
async def register_batch():
    analyze_batch_task.delay()
    return {"message": "batch registered."}


@router.post("/register/all")
async def register_batch_all():
    await PostAnalyzer().register_all()
    return {"message": "all batch registered."}


@router.post("/submit")
async def submit_all_batches():
    await PostAnalyzer().submit_batch()
    return {"message": "batch submitted."}

@router.post("/check")
async def check_batch_status():
    await PostAnalyzer().check_batch_status()
    return {"message": "batch status checked."}

@router.post("/complete")
async def complete_jobs() -> JobCompletionResult:
    return await PostAnalyzer().complete_jobs()
