import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assistant, auth, evaluation, jobs, recommendations, resume, users
from app.core.config import settings
from app.database.session import init_db
from app.services import embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    threading.Thread(target=embeddings.warmup, daemon=True).start()
    yield


app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(resume.router)
app.include_router(jobs.router)
app.include_router(assistant.router)
app.include_router(recommendations.router)
app.include_router(evaluation.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}