from contextlib import asynccontextmanager

from fastapi import FastAPI

from utils import Logger
from routes import root_router


logger = Logger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger.debug("Registered Routes:")
    for route in fastapi_app.routes:
        logger.debug(f"  {route}")
    yield
app = FastAPI(lifespan=lifespan)
app.include_router(root_router)

@app.get("/healthcheck")
def healthcheck():
    logger.info("Health Checked.")
    return {"status": "active"}



