import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-123456")
os.environ["GEMINI_API_KEY"] = ""  # tests must never call the real Gemini API

import hashlib
import math
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import EMBED_DIM
from app.database.session import Base, get_db
from app.main import app
from app.models import job, resume, user  # noqa: F401
from app.services import embeddings


def fake_embed_texts(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder: shared words => similar vectors. No download."""
    out = []
    for text in texts:
        vec = [0.0] * EMBED_DIM
        for token in re.findall(r"[a-z0-9+#.]+", text.lower()):
            vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % EMBED_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / norm for x in vec])
    return out


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_texts", fake_embed_texts)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)  # no "with": skips startup (pgvector, model warm-up) in tests
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    creds = {"email": "resume@example.com", "password": "StrongPass123", "full_name": "Resume User"}
    client.post("/api/auth/register", json=creds)
    r = client.post("/api/auth/login", data={"username": creds["email"], "password": creds["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}