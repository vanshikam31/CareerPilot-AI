import math

import pytest

from app.evaluation import retrieval_eval
from app.evaluation.agent_metrics import citation_report, extract_citations
from app.evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank
from app.services.job_ingest import ingest_csv, ingest_rows
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
    dict(title="Frontend Developer", company="PixelForge", location="Gurgaon", work_mode="hybrid",
         experience_level="mid", category="Frontend", skills=["React", "JavaScript", "CSS"],
         description="Build responsive user interfaces."),
]

MINI_DATASET = {
    "queries": [
        {"id": "a", "split": "dev", "query": "rag embeddings chatbots llm agents",
         "expected_titles": ["AI Engineer"], "key_skills": ["RAG", "LLMs", "LangChain"], "category": "AI/ML"},
        {"id": "b", "split": "dev", "query": "rest apis fastapi postgresql docker",
         "expected_titles": ["Backend Engineer"], "key_skills": ["FastAPI", "PostgreSQL", "Docker"], "category": "Backend"},
        {"id": "c", "split": "test", "query": "dashboards power bi tableau sql",
         "expected_titles": ["Data Analyst"], "key_skills": ["SQL", "Power BI", "Tableau"], "category": "Data"},
    ],
    "profiles": [
        {"id": "p", "profile": {"skills": ["Python", "FastAPI", "PostgreSQL"], "target_roles": ["Backend Engineer"],
                                "preferred_locations": ["Noida"], "experience_level": "junior"},
         "expected_titles": ["Backend Engineer"], "key_skills": ["FastAPI", "PostgreSQL", "Docker"], "category": "Backend"},
    ],
}


@pytest.fixture()
def seeded(session_factory):
    with session_factory() as db:
        ingest_rows(db, ROWS)


# ---------- metrics ----------
def test_precision_and_recall():
    ranked = [3, 0, 2, 0, 1]
    assert precision_at_k(ranked, 5) == pytest.approx(0.4)  # grades 3 and 2 are relevant
    assert recall_at_k(ranked, 5, total_relevant=4) == pytest.approx(0.5)
    assert recall_at_k(ranked, 5, total_relevant=0) == 0.0


def test_ndcg():
    assert ndcg_at_k([3, 2, 0], [3, 2, 0, 0], 10) == pytest.approx(1.0)  # perfect order
    # relevant job at rank 2 instead of rank 1
    assert ndcg_at_k([0, 3], [3, 0, 0], 2) == pytest.approx(1 / math.log2(3))
    assert ndcg_at_k([0, 0], [0, 0], 10) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank([0, 0, 3]) == pytest.approx(1 / 3)
    assert reciprocal_rank([0, 1, 0]) == 0.0  # grade 1 is not "relevant"


# ---------- citations ----------
def test_citation_report():
    reply = "- [job #3] Backend Engineer at Orbit Tech\n- [job #31] Something else\n"
    jobs = {3: ("Backend Engineer", "Orbit Tech"), 31: ("Data Analyst", "Zenith")}
    assert extract_citations(reply) == [3, 31]
    report = citation_report(reply, {3}, jobs)
    assert report == {"cited": 2, "grounded": 1, "checked": 2, "consistent": 1}


# ---------- dataset and pipeline ----------
SAMPLE_CSV = retrieval_eval.DATA_DIR / "sample_jobs.csv"


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="run data/generate_jobs.py first")
def test_every_eval_case_has_relevant_jobs(session_factory):
    dataset = retrieval_eval.load_dataset()
    assert sum(1 for q in dataset["queries"] if q["split"] == "dev") >= 5
    assert sum(1 for q in dataset["queries"] if q["split"] == "test") >= 5
    with session_factory() as db:
        ingest_csv(db, SAMPLE_CSV)
        for case in [*dataset["queries"], *dataset["profiles"]]:
            scope = retrieval_eval.jobs_in_scope(db, case)
            relevant = [j for j in scope if retrieval_eval.grade(j, case) >= 2]
            assert relevant, f"case {case['id']} has no relevant job"


def test_run_evaluation_report(session_factory, seeded):
    with session_factory() as db:
        report = retrieval_eval.run_evaluation(db, MINI_DATASET)
    dev = report["retrieval"]["dev"]
    assert dev["n"] == 2 and report["retrieval"]["test"]["n"] == 1
    assert set(dev) >= {"keyword", "semantic", "hybrid_default", "hybrid_tuned"}
    assert dev["hybrid_default"]["ndcg@10"] > 0.9
    assert len(report["tuning"]["grid"]) == 11
    assert 0.0 <= report["tuning"]["best_semantic_weight"] <= 1.0
    assert report["personalisation"]["n"] == 1
    assert report["personalisation"]["personalized_ranker"]["ndcg@10"] > 0
    assert "hybrid_default" in retrieval_eval.to_markdown(report)


def test_run_evaluation_needs_jobs(session_factory):
    with session_factory() as db:
        with pytest.raises(ValueError):
            retrieval_eval.run_evaluation(db, MINI_DATASET)


# ---------- agent metrics API ----------
def test_agent_metrics_endpoint(client, auth_headers, seeded, monkeypatch):
    use_llm(
        monkeypatch,
        calls("search_jobs", query="rag embeddings chatbots llm"),
        say("Try [job #1] AI Engineer at Nimbus Labs, or [job #999] Ghost Corp."),
    )
    chat(client, auth_headers, "llm chatbots")
    r = client.get("/api/evaluation/agent", headers=auth_headers)
    assert r.status_code == 200
    m = r.json()
    assert m["replies"] == 1 and m["gemini_replies"] == 1 and m["fallback_rate"] == 0.0
    assert m["tool_calls"] == 1 and m["tool_call_success_rate"] == 1.0
    assert m["citations_total"] == 2
    assert m["citation_grounding_rate"] == 0.5  # job 999 was never shown by a tool
    assert m["citation_consistency_rate"] == 1.0
    assert m["latency_avg_ms"] is not None