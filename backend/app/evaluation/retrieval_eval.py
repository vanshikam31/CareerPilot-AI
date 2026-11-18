"""Offline evaluation of search and ranking against a labelled dataset.

Relevance grades are rule-based (not human labels):
  3 = job title contains an expected title
  2 = job has >= 3 of the case's key skills
  1 = same category
  0 = otherwise
Cases that state an experience level cap the grade at 1 for jobs 2+ levels away.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.evaluation import metrics
from app.evaluation.metrics import RELEVANT
from app.models.job import Job
from app.models.user import UserProfile
from app.recommendations.ranker import LEVEL_ORDER
from app.recommendations.service import recommend
from app.retrieval.search import SearchFilters, _filtered, profile_query, search_jobs

ROOT = Path(__file__).resolve().parents[3]  # .../CareerPilot-AI
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
DATASET_PATH = DATA_DIR / "evaluation_dataset.json"
REPORT_PATH = DATA_DIR / "evaluation_report.json"

DEFAULT_WEIGHTS = (0.7, 0.3)
GRID = [round(i / 10, 1) for i in range(11)]  # semantic weight 0.0 ... 1.0
METRIC_KEYS = ("p@5", "r@10", "ndcg@10", "mrr")

NOTES = [
    "Jobs are synthetic and relevance labels are rule-based (title, key skills, category). "
    "Scores are optimistic and show consistency, not real hiring relevance.",
    "Hybrid weights are tuned on the dev split only. The test split is small, so differences are noisy.",
    "Personalisation labels share an assumption (experience level) with the ranker: a sanity check, not proof.",
]


def load_dataset(path: Path = DATASET_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def grade(job: Job, case: dict) -> int:
    title = job.title.lower()
    if any(t.lower() in title for t in case["expected_titles"]):
        g = 3
    elif len({s.lower() for s in case["key_skills"]} & {s.lower() for s in (job.skills or [])}) >= 3:
        g = 2
    elif job.category == case["category"]:
        g = 1
    else:
        g = 0
    level = case.get("experience_level") or (case.get("profile") or {}).get("experience_level")
    if level in LEVEL_ORDER and job.experience_level in LEVEL_ORDER:
        if abs(LEVEL_ORDER[level] - LEVEL_ORDER[job.experience_level]) >= 2:
            g = min(g, 1)
    return g


def jobs_in_scope(db: Session, case: dict) -> list[Job]:
    """Jobs that pass the case's filters. Recall and the ideal ranking are computed over these."""
    filters = SearchFilters(**case.get("filters", {}))
    return list(db.scalars(_filtered(select(Job), filters)).all())


def score_case(ranked_jobs: list[Job], scope: list[Job], case: dict) -> dict | None:
    ranked = [grade(j, case) for j in ranked_jobs]
    all_rels = [grade(j, case) for j in scope]
    total_relevant = sum(1 for r in all_rels if r >= RELEVANT)
    if total_relevant == 0:
        return None  # nothing to find: skip rather than count it as a failure
    return {
        "p@5": metrics.precision_at_k(ranked, 5),
        "r@10": metrics.recall_at_k(ranked, 10, total_relevant),
        "ndcg@10": metrics.ndcg_at_k(ranked, all_rels, 10),
        "mrr": metrics.reciprocal_rank(ranked),
    }


def average(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in METRIC_KEYS}


def evaluate_system(db: Session, cases: list[dict], ranker_fn) -> dict | None:
    rows = []
    for case in cases:
        row = score_case(ranker_fn(case), jobs_in_scope(db, case), case)
        if row:
            rows.append(row)
    return average(rows)


# ---------- the systems being compared ----------
def _search_fn(db: Session, mode: str, weights: tuple[float, float] | None = None):
    def run(case: dict) -> list[Job]:
        filters = SearchFilters(**case.get("filters", {}))
        hits = search_jobs(db, case["query"], filters, mode=mode, limit=10, weights=weights)
        return [h.job for h in hits]

    return run


def _profile_of(case: dict) -> UserProfile:
    p = case["profile"]
    return UserProfile(
        skills=p.get("skills", []),
        target_roles=p.get("target_roles", []),
        preferred_locations=p.get("preferred_locations", []),
        experience_level=p.get("experience_level"),
    )


def _plain_profile_search(db: Session):
    def run(case: dict) -> list[Job]:
        hits = search_jobs(db, profile_query(_profile_of(case)), mode="hybrid", limit=10)
        return [h.job for h in hits]

    return run


def _personalised_ranker(db: Session):
    def run(case: dict) -> list[Job]:
        return [r.job for r in recommend(db, _profile_of(case), limit=10)]  # same code path as the API

    return run


def tune_weights(db: Session, dev_cases: list[dict]) -> tuple[float, list[dict]]:
    """Grid search over the semantic weight, scored by NDCG@10 on the dev split."""
    grid = []
    for w in GRID:
        avg = evaluate_system(db, dev_cases, _search_fn(db, "hybrid", (w, round(1 - w, 1))))
        grid.append({"w_sem": w, "ndcg@10": avg["ndcg@10"] if avg else 0.0})
    # Ties go to the weight closest to the current default (0.7).
    best = max(grid, key=lambda g: (g["ndcg@10"], -abs(g["w_sem"] - DEFAULT_WEIGHTS[0])))
    return best["w_sem"], grid


def run_evaluation(db: Session, dataset: dict) -> dict:
    num_jobs = db.scalar(select(func.count()).select_from(Job)) or 0
    if num_jobs == 0:
        raise ValueError("No jobs in the database. Run seed_jobs.py first.")

    queries = dataset["queries"]
    splits = {name: [q for q in queries if q.get("split") == name] for name in ("dev", "test")}

    best_w, grid = tune_weights(db, splits["dev"])
    tuned = (best_w, round(1 - best_w, 1))
    systems = {
        "keyword": _search_fn(db, "keyword"),
        "semantic": _search_fn(db, "semantic"),
        "hybrid_default": _search_fn(db, "hybrid", DEFAULT_WEIGHTS),
        "hybrid_tuned": _search_fn(db, "hybrid", tuned),
    }
    retrieval = {}
    for split, cases in splits.items():
        entry = {"n": len(cases)}
        for name, fn in systems.items():
            entry[name] = evaluate_system(db, cases, fn)
        retrieval[split] = entry

    profiles = dataset.get("profiles", [])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "num_jobs": num_jobs,
        "num_queries": len(queries),
        "retrieval": retrieval,
        "tuning": {"tuned_on": "dev", "best_semantic_weight": best_w, "grid": grid},
        "personalisation": {
            "n": len(profiles),
            "hybrid_profile_query": evaluate_system(db, profiles, _plain_profile_search(db)),
            "personalized_ranker": evaluate_system(db, profiles, _personalised_ranker(db)),
        },
        "notes": NOTES,
    }


def _row(name: str, m: dict | None) -> str:
    if not m:
        return f"| {name} | - | - | - | - |"
    return f"| {name} | {m['p@5']:.3f} | {m['r@10']:.3f} | {m['ndcg@10']:.3f} | {m['mrr']:.3f} |"


def to_markdown(report: dict) -> str:
    head = ["| System | P@5 | R@10 | NDCG@10 | MRR |", "|---|---|---|---|---|"]
    lines = [
        "# CareerPilot evaluation report",
        "",
        f"Generated: {report['generated_at']} | Jobs: {report['num_jobs']} | Queries: {report['num_queries']}",
    ]
    for split in ("dev", "test"):
        entry = report["retrieval"][split]
        lines += ["", f"## Retrieval: {split} split ({entry['n']} queries)", "", *head]
        for name in ("keyword", "semantic", "hybrid_default", "hybrid_tuned"):
            lines.append(_row(name, entry[name]))
    t = report["tuning"]
    lines += ["", f"Best semantic weight on dev: {t['best_semantic_weight']} (default is 0.7).", "",
              "| Semantic weight | NDCG@10 (dev) |", "|---|---|"]
    lines += [f"| {g['w_sem']} | {g['ndcg@10']:.3f} |" for g in t["grid"]]
    p = report["personalisation"]
    lines += ["", f"## Personalisation ({p['n']} profiles)", "", *head,
              _row("hybrid_profile_query", p["hybrid_profile_query"]),
              _row("personalized_ranker", p["personalized_ranker"]), "", "## Notes", ""]
    lines += [f"- {note}" for note in report["notes"]]
    return "\n".join(lines) + "\n"