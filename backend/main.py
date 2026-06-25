import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db.supabase_client import init_db
from api.routers import document, interview

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("Application startup complete. Database is ready.")


app.include_router(document.router)
app.include_router(interview.router)


@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )
