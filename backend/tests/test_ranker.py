from types import SimpleNamespace

import pytest

from app.recommendations.ranker import (
    WEIGHTS,
    UserSignals,
    level_fit,
    location_fit,
    rank_jobs,
    role_fit,
    skill_match,
)
from app.recommendations.service import learning_path


def make_job(id, title, location="Noida", work_mode="onsite", level="fresher", skills=()):
    return SimpleNamespace(
        id=id, title=title, location=location, work_mode=work_mode,
        experience_level=level, skills=list(skills),
    )


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_level_fit():
    assert level_fit("fresher", "fresher") == 1.0
    assert level_fit("fresher", "junior") == 0.5
    assert level_fit("fresher", "mid") == 0.15
    assert level_fit("fresher", "senior") == 0.0
    assert level_fit(None, "junior") == 0.5  # unknown level is neutral


def test_skill_match():
    score, matched, missing = skill_match(["python", "SQL"], ["Python", "SQL", "Docker"])
    assert score == pytest.approx(2 / 3)
    assert matched == ["Python", "SQL"]
    assert missing == ["Docker"]
    assert skill_match(["Python"], []) == (0.0, [], [])


def test_location_fit():
    onsite = make_job(1, "X", location="Noida")
    remote = make_job(2, "X", location="Remote", work_mode="remote")
    assert location_fit(["noida"], onsite) == 1.0
    assert location_fit(["Pune"], onsite) == 0.0
    assert location_fit(["Pune"], remote) == 1.0
    assert location_fit([], onsite) == 0.5


def test_role_fit():
    assert role_fit(["AI Engineer"], "Associate AI Engineer") == 1.0
    assert role_fit(["AI Engineer"], "Backend Engineer (Python)") == 0.0  # "engineer" alone is not a match
    assert role_fit([], "Anything") == 0.5


def test_rank_jobs_score_and_order():
    user = UserSignals(["Python", "FastAPI", "PostgreSQL"], ["Backend Engineer"], ["Noida"], "fresher")
    good = make_job(1, "Backend Engineer (Python)", skills=["Python", "FastAPI", "PostgreSQL", "Docker"])
    poor = make_job(2, "Data Analyst", location="Pune", level="senior", skills=["SQL", "Power BI"])
    ranked = rank_jobs(user, [(good, 0.6), (poor, 0.6)])
    assert [r.job.id for r in ranked] == [1, 2]
    # 0.35*0.5 (neutral semantic) + 0.30*0.75 + 0.15 + 0.10 + 0.10
    assert ranked[0].score == pytest.approx(0.75)
    assert ranked[0].matched_skills == ["Python", "FastAPI", "PostgreSQL"]
    assert ranked[0].missing_skills == ["Docker"]


def test_reasons_are_generated():
    user = UserSignals(["Python", "FastAPI", "PostgreSQL"], ["Backend Engineer"], ["Noida"], "fresher")
    job = make_job(1, "Backend Engineer (Python)", skills=["Python", "FastAPI", "PostgreSQL", "Docker"])
    reasons = rank_jobs(user, [(job, 0.6)])[0].reasons
    assert reasons[0] == "You already have 3 of 4 required skills: Python, FastAPI, PostgreSQL."
    assert "Skills to learn: Docker." in reasons
    assert "Experience level fits (fresher)." in reasons
    assert "Located in Noida, one of your preferred locations." in reasons


def test_learning_path_counts_missing_skills():
    user = UserSignals(["Python"], [], [], None)
    jobs = [
        make_job(1, "A", skills=["Python", "Docker", "AWS"]),
        make_job(2, "B", skills=["Docker", "Kubernetes"]),
        make_job(3, "C", skills=["Docker", "AWS"]),
    ]
    recs = rank_jobs(user, [(j, 0.5) for j in jobs])
    path = learning_path(recs)
    assert path[0] == {"skill": "Docker", "jobs_needing_it": 3, "percent_of_top_jobs": 100}
    assert [p["skill"] for p in path] == ["Docker", "AWS", "Kubernetes"]