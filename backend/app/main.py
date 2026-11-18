import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, jobs, resume, users
from app.core.config import settings
from app.database.session import init_db
from app.services import embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Load the embedding model in the background so the first search isn't slow,
    # without delaying server startup.
    threading.Thread(target=embeddings.warmup, daemon=True).start()
    yield


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend URL before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(resume.router)
app.include_router(jobs.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}