import pytest

from app.agents import agent
from app.agents.types import ToolCall, Turn
from app.services.job_ingest import ingest_rows

ROWS = [
    dict(title="AI Engineer", company="Nimbus Labs", location="Gurgaon", work_mode="hybrid",
         experience_level="fresher", category="AI/ML", skills=["Python", "LLMs", "RAG", "LangChain"],
         description="Build retrieval augmented chatbots and LLM agents with embeddings."),
    dict(title="Backend Engineer", company="Orbit Tech", location="Noida", work_mode="onsite",
         experience_level="junior", category="Backend", skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
         description="Design REST APIs and database schemas for a SaaS product."),
]


class FakeLLM:
    """Plays back a script of Turns (or raises an Exception) instead of calling Gemini."""

    def __init__(self, script):
        self.script = list(script)
        self.systems, self.histories, self.tool_flags, self.results = [], [], [], []

    def start(self, history, message):
        self.histories.append(history)
        return []

    def generate(self, contents, system, allow_tools=True):
        self.systems.append(system)
        self.tool_flags.append(allow_tools)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def add_tool_results(self, contents, turn, results):
        self.results.extend(results)  # list of (ToolCall, result dict)


def use_llm(monkeypatch, *script):
    fake = FakeLLM(script)
    monkeypatch.setattr(agent, "get_llm", lambda: fake)
    return fake


def calls(name, **args):
    return Turn(calls=[ToolCall(name, args)])


def say(text):
    return Turn(text=text)


def chat(client, headers, message, conversation_id=None):
    return client.post(
        "/api/agent/chat",
        json={"message": message, "conversation_id": conversation_id},
        headers=headers,
    )


@pytest.fixture()
def seeded(session_factory):
    with session_factory() as db:
        ingest_rows(db, ROWS)


def test_chat_requires_auth(client):
    assert client.post("/api/agent/chat", json={"message": "hi"}).status_code == 401


def test_chat_validation(client, auth_headers):
    assert chat(client, auth_headers, "").status_code == 422


def test_fallback_when_no_gemini_key(client, auth_headers, seeded):
    r = chat(client, auth_headers, "python fastapi postgresql backend apis")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback"
    assert "Backend Engineer" in body["reply"]
    assert body["tool_calls"][0]["name"] == "search_jobs"
    assert body["conversation_id"] > 0


def test_agent_tool_loop(client, auth_headers, seeded, monkeypatch):
    fake = use_llm(
        monkeypatch,
        calls("search_jobs", query="rag embeddings chatbots llm"),
        say("Try [job #1] AI Engineer at Nimbus Labs."),
    )
    r = chat(client, auth_headers, "I want to build LLM chatbots")
    body = r.json()
    assert body["source"] == "gemini"
    assert "AI Engineer" in body["reply"]
    assert body["tool_calls"] == [
        {"name": "search_jobs", "args": {"query": "rag embeddings chatbots llm"}, "ok": True}
    ]
    _, result = fake.results[0]
    assert result["jobs"][0]["title"] == "AI Engineer"


def test_unknown_tool_is_reported_not_fatal(client, auth_headers, seeded, monkeypatch):
    use_llm(monkeypatch, calls("hack_the_planet"), say("Sorry, I could not do that."))
    body = chat(client, auth_headers, "do something odd").json()
    assert body["source"] == "gemini"
    assert body["tool_calls"][0]["ok"] is False


def test_bad_tool_arguments(client, auth_headers, seeded, monkeypatch):
    fake = use_llm(
        monkeypatch,
        calls("search_jobs", query="python", work_mode="moon"),
        say("No luck."),
    )
    body = chat(client, auth_headers, "python jobs on the moon").json()
    assert body["tool_calls"][0]["ok"] is False
    _, result = fake.results[0]
    assert "work_mode" in result["error"]


def test_skill_gap_tool(client, auth_headers, seeded, monkeypatch):
    client.put("/api/users/me/profile", json={"skills": ["Python", "SQL"]}, headers=auth_headers)
    fake = use_llm(monkeypatch, calls("skill_gap", job_id=1), say("You match 25 percent."))
    chat(client, auth_headers, "how well do I fit job 1?")
    _, result = fake.results[0]
    assert result["matched"] == ["Python"]
    assert result["missing"] == ["LLMs", "RAG", "LangChain"]
    assert result["match_percent"] == 25


def test_memory_saved_listed_and_used(client, auth_headers, seeded, monkeypatch):
    use_llm(monkeypatch, calls("save_preference", fact="Prefers Gurgaon, hybrid roles"), say("Saved."))
    chat(client, auth_headers, "I prefer hybrid jobs in Gurgaon")

    memories = client.get("/api/agent/memories", headers=auth_headers).json()
    assert [m["content"] for m in memories] == ["Prefers Gurgaon, hybrid roles"]

    fake = use_llm(monkeypatch, say("Hello again"))
    chat(client, auth_headers, "hi")
    assert "Prefers Gurgaon" in fake.systems[0]  # long-term memory reaches the prompt

    assert client.delete(f"/api/agent/memories/{memories[0]['id']}", headers=auth_headers).status_code == 204
    assert client.get("/api/agent/memories", headers=auth_headers).json() == []


def test_conversation_history_is_sent(client, auth_headers, seeded, monkeypatch):
    fake = use_llm(monkeypatch, say("one"), say("two"))
    cid = chat(client, auth_headers, "first question").json()["conversation_id"]
    chat(client, auth_headers, "second question", cid)
    assert fake.histories[0] == []
    assert len(fake.histories[1]) == 2
    assert fake.histories[1][0]["content"] == "first question"


def test_llm_error_falls_back(client, auth_headers, seeded, monkeypatch):
    use_llm(monkeypatch, RuntimeError("429 quota exceeded"))
    r = chat(client, auth_headers, "python fastapi backend")
    assert r.status_code == 200
    assert r.json()["source"] == "fallback"


def test_step_limit_forces_final_answer(client, auth_headers, seeded, monkeypatch):
    fake = use_llm(monkeypatch, *([calls("search_jobs", query="python")] * 5), say("Final answer"))
    body = chat(client, auth_headers, "keep searching forever").json()
    assert body["reply"] == "Final answer"
    assert fake.tool_flags == [True] * 5 + [False]


def test_messages_list_and_delete(client, auth_headers, seeded):
    cid = chat(client, auth_headers, "python backend").json()["conversation_id"]
    messages = client.get(f"/api/agent/conversations/{cid}", headers=auth_headers).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert len(client.get("/api/agent/conversations", headers=auth_headers).json()) == 1
    assert client.delete(f"/api/agent/conversations/{cid}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/agent/conversations/{cid}", headers=auth_headers).status_code == 404


def test_conversations_are_private(client, auth_headers, seeded):
    cid = chat(client, auth_headers, "python backend").json()["conversation_id"]
    other = {"email": "other@example.com", "password": "StrongPass123", "full_name": "Other"}
    client.post("/api/auth/register", json=other)
    token = client.post("/api/auth/login", data={"username": other["email"], "password": other["password"]})
    headers2 = {"Authorization": f"Bearer {token.json()['access_token']}"}
    assert client.get(f"/api/agent/conversations/{cid}", headers=headers2).status_code == 404
    assert chat(client, headers2, "hello", cid).status_code == 404