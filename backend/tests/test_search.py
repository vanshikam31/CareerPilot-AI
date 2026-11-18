import pytest

from app.retrieval.search import tokenize
from app.services.job_ingest import ingest_rows

ROWS = [
    dict(title="AI Engineer", company="Nimbus Labs", location="Gurgaon", work_mode="hybrid",
         experience_level="fresher", category="AI/ML", skills=["Python", "LLMs", "RAG", "LangChain"],
         description="Build retrieval augmented chatbots and LLM agents with embeddings."),
    dict(title="Backend Engineer", company="Orbit Tech", location="Noida", work_mode="onsite",
         experience_level="junior", category="Backend", skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
         description="Design REST APIs and database schemas for a SaaS product."),
    dict(title="Data Analyst", company="Zenith Analytics", location="Remote", work_mode="remote",
         experience_level="junior", category="Data", skills=["SQL", "Power BI", "Tableau"],
         description="Create dashboards and reports from business data."),
    dict(title="Frontend Developer", company="PixelForge", location="Gurgaon", work_mode="hybrid",
         experience_level="mid", category="Frontend", skills=["React", "JavaScript", "CSS"],
         description="Build responsive user interfaces."),
]


@pytest.fixture()
def seeded(session_factory):
    with session_factory() as db:
        ingest_rows(db, ROWS)


def search(client, headers, **body):
    body.setdefault("query", "engineer developer analyst python")
    return client.post("/api/jobs/search", json=body, headers=headers)


def titles(response):
    return [hit["job"]["title"] for hit in response.json()]


# ---------- unit tests ----------
def test_tokenize():
    assert tokenize("Node.js, C++ and Python.") == ["node.js", "c++", "python"]
    assert tokenize("python PYTHON python") == ["python"]


def test_ingest_is_idempotent(session_factory):
    with session_factory() as db:
        assert ingest_rows(db, ROWS) == (4, 0)
        assert ingest_rows(db, ROWS) == (0, 4)


def test_ingest_rejects_bad_row(session_factory):
    bad = {**ROWS[0], "work_mode": "moon"}
    with session_factory() as db:
        with pytest.raises(ValueError):
            ingest_rows(db, [bad])


# ---------- API tests ----------
def test_search_requires_auth(client):
    assert client.post("/api/jobs/search", json={"query": "python"}).status_code == 401


def test_semantic_search_ranks_relevant_first(client, auth_headers, seeded):
    r = search(client, auth_headers, query="rag embeddings chatbots llm agents")
    assert r.status_code == 200
    assert titles(r)[0] == "AI Engineer"
    hits = r.json()
    assert 0 < hits[0]["score"] <= 1
    assert hits[0]["semantic_score"] > hits[-1]["semantic_score"]


def test_keyword_mode_title_match(client, auth_headers, seeded):
    r = search(client, auth_headers, query="React", mode="keyword")
    assert titles(r) == ["Frontend Developer"]
    assert r.json()[0]["semantic_score"] == 0


def test_location_filter(client, auth_headers, seeded):
    r = search(client, auth_headers, location="gurgaon", include_remote=False)
    assert set(titles(r)) == {"AI Engineer", "Frontend Developer"}
    r = search(client, auth_headers, location="gurgaon")  # remote jobs included by default
    assert set(titles(r)) == {"AI Engineer", "Frontend Developer", "Data Analyst"}


def test_work_mode_and_level_filters(client, auth_headers, seeded):
    assert titles(search(client, auth_headers, work_mode="onsite")) == ["Backend Engineer"]
    r = search(client, auth_headers, experience_level="junior")
    assert set(titles(r)) == {"Backend Engineer", "Data Analyst"}
    r = search(client, auth_headers, work_mode="remote", experience_level="junior")
    assert titles(r) == ["Data Analyst"]


def test_filter_with_no_match(client, auth_headers, seeded):
    r = search(client, auth_headers, location="Mumbai", include_remote=False)
    assert r.status_code == 200
    assert r.json() == []


def test_invalid_work_mode(client, auth_headers, seeded):
    assert search(client, auth_headers, work_mode="moon").status_code == 422


def test_for_me_requires_profile(client, auth_headers, seeded):
    assert client.get("/api/jobs/for-me", headers=auth_headers).status_code == 400


def test_for_me_uses_profile(client, auth_headers, seeded):
    client.put(
        "/api/users/me/profile",
        json={"skills": ["Python", "FastAPI", "PostgreSQL"], "target_roles": ["Backend Engineer"]},
        headers=auth_headers,
    )
    r = client.get("/api/jobs/for-me", headers=auth_headers)
    assert r.status_code == 200
    assert titles(r)[0] == "Backend Engineer"


def test_for_me_resume_404(client, auth_headers, seeded):
    assert client.get("/api/jobs/for-me?source=resume", headers=auth_headers).status_code == 404


def test_get_job(client, auth_headers, seeded):
    job_id = search(client, auth_headers, query="React", mode="keyword").json()[0]["job"]["id"]
    r = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Frontend Developer"


def test_get_job_404(client, auth_headers):
    assert client.get("/api/jobs/99999", headers=auth_headers).status_code == 404