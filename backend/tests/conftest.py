import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-123456")
os.environ["GEMINI_API_KEY"] = ""  # tests must never call the real Gemini API

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import app
from app.models import resume, user  # noqa: F401


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)  # no "with": skips startup (pgvector) in tests
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    creds = {"email": "resume@example.com", "password": "StrongPass123", "full_name": "Resume User"}
    client.post("/api/auth/register", json=creds)
    r = client.post("/api/auth/login", data={"username": creds["email"], "password": creds["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}