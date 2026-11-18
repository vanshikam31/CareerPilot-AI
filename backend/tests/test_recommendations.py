import pytest
from sqlalchemy import select

from app.agents.tools import ToolContext, run_tool
from app.models.user import User
from app.services.job_ingest import ingest_rows
from test_agent import calls, chat, say, use_llm

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
    dict(title="Senior Backend Engineer (Python)", company="Nova Stack", location="Delhi", work_mode="hybrid",
         experience_level="senior", category="Backend", skills=["Python", "FastAPI", "PostgreSQL", "Docker", "SQLAlchemy"],
         description="Lead the design of Python backend services and APIs."),
]

PROFILE = {
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "target_roles": ["Backend Engineer"],
    "preferred_locations": ["Noida"],
    "experience_level": "junior",
}


@pytest.fixture()
def seeded(session_factory):
    with session_factory() as db:
        ingest_rows(db, ROWS)


def set_profile(client, headers):
    assert client.put("/api/users/me/profile", json=PROFILE, headers=headers).status_code == 200


def test_requires_auth(client):
    assert client.get("/api/recommendations").status_code == 401


def test_needs_profile(client, auth_headers, seeded):
    assert client.get("/api/recommendations", headers=auth_headers).status_code == 400
    assert client.get("/api/recommendations/learning-path", headers=auth_headers).status_code == 400


def test_recommendations_are_ranked_and_explained(client, auth_headers, seeded):
    set_profile(client, auth_headers)
    r = client.get("/api/recommendations", headers=auth_headers)
    assert r.status_code == 200
    recs = r.json()
    top = recs[0]
    assert top["job"]["title"] == "Backend Engineer"
    assert top["matched_skills"] == ["Python", "FastAPI", "PostgreSQL"]
    assert top["missing_skills"] == ["Docker"]
    assert set(top["breakdown"]) == {"semantic", "skills", "role", "level", "location"}
    assert top["reasons"]
    scores = [x["score"] for x in recs]
    assert scores == sorted(scores, reverse=True)


def test_location_param_filters(client, auth_headers, seeded):
    set_profile(client, auth_headers)
    r = client.get("/api/recommendations?location=Noida", headers=auth_headers)
    assert {x["job"]["title"] for x in r.json()} == {"Backend Engineer", "Data Analyst"}  # Noida + remote


def test_learning_path(client, auth_headers, seeded):
    set_profile(client, auth_headers)
    body = client.get("/api/recommendations/learning-path", headers=auth_headers).json()
    assert body["based_on_jobs"] == 4
    assert body["skills"][0] == {"skill": "Docker", "jobs_needing_it": 2, "percent_of_top_jobs": 50}


def test_skill_gap_endpoint(client, auth_headers, seeded):
    set_profile(client, auth_headers)
    jobs = client.get("/api/jobs", headers=auth_headers).json()
    backend_id = next(j["id"] for j in jobs if j["title"] == "Backend Engineer")
    r = client.get(f"/api/recommendations/skill-gap/{backend_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["matched"] == ["Python", "FastAPI", "PostgreSQL"]
    assert body["missing"] == ["Docker"]
    assert body["match_percent"] == 75


def test_skill_gap_404(client, auth_headers):
    assert client.get("/api/recommendations/skill-gap/9999", headers=auth_headers).status_code == 404


def test_agent_tools_recommend_and_learning_path(client, auth_headers, session_factory, seeded):
    set_profile(client, auth_headers)
    with session_factory() as db:
        user = db.scalar(select(User))
        result, ok = run_tool(ToolContext(db, user), "recommend_jobs", {"limit": 2})
        assert ok and result["count"] == 2
        assert result["jobs"][0]["title"] == "Backend Engineer"
        assert result["jobs"][0]["reasons"]
        result, ok = run_tool(ToolContext(db, user), "learning_path", {})
        assert ok and result["skills_to_learn"][0]["skill"] == "Docker"


def test_agent_tool_without_profile_returns_error(client, auth_headers, session_factory, seeded):
    with session_factory() as db:
        user = db.scalar(select(User))
        result, ok = run_tool(ToolContext(db, user), "recommend_jobs", {})
    assert ok is False
    assert "profile" in result["error"]


def test_trace_records_job_ids(client, auth_headers, seeded, monkeypatch):
    use_llm(
        monkeypatch,
        calls("search_jobs", query="rag embeddings chatbots llm"),
        say("Try [job #1] AI Engineer at Nimbus Labs."),
    )
    cid = chat(client, auth_headers, "llm chatbots").json()["conversation_id"]
    messages = client.get(f"/api/agent/conversations/{cid}", headers=auth_headers).json()
    trace = messages[-1]["tool_calls"]
    assert trace[0]["job_ids"]
    assert all(isinstance(i, int) for i in trace[0]["job_ids"])