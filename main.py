from contextlib import asynccontextmanager

from fastapi import FastAPI

from server import logger
import client



@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger.debug("Registered Routes:")
    for route in fastapi_app.routes:
        logger.debug(f"  {route}")
    yield
app = FastAPI(lifespan=lifespan)
app.include_router(client.router)

@app.get("/healthcheck")
def healthcheck():
    logger.info("Health Checked.")
    return {"status": "active"}



