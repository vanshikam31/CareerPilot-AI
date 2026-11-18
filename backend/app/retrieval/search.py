import math
import re
from dataclasses import dataclass

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.user import UserProfile
from app.services import embeddings

CANDIDATES = 50
# (semantic weight, keyword weight). Heuristic for now; tuned with NDCG in Phase 5.
WEIGHTS = {"hybrid": (0.7, 0.3), "semantic": (1.0, 0.0), "keyword": (0.0, 1.0)}

STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "for", "with", "of", "to", "i", "am", "at", "on",
    "is", "are", "my", "me", "looking", "job", "jobs", "role", "roles", "skills", "skill",
    "experience", "level", "who", "know", "knows", "want", "need",
}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*")  # keeps c++, c#, node.js


@dataclass
class SearchFilters:
    location: str | None = None
    include_remote: bool = True
    work_mode: str | None = None
    experience_level: str | None = None


@dataclass
class SearchHit:
    job: Job
    score: float
    semantic_score: float
    keyword_score: float


def tokenize(text: str) -> list[str]:
    tokens = (t.strip(".") for t in _TOKEN_RE.findall(text.lower()))
    return list(dict.fromkeys(t for t in tokens if t and t not in STOPWORDS))


def keyword_score(query_tokens: list[str], job: Job) -> float:
    """0..1. A query word found in the title counts 3, in skills 2, in the description 1."""
    if not query_tokens:
        return 0.0
    title = set(tokenize(job.title))
    skills = set(tokenize(" ".join(job.skills or [])))
    body = set(tokenize(job.description))
    total = 0
    for token in query_tokens:
        if token in title:
            total += 3
        elif token in skills:
            total += 2
        elif token in body:
            total += 1
    return total / (3 * len(query_tokens))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _filtered(stmt: Select, f: SearchFilters) -> Select:
    if f.location:
        cond = Job.location.ilike(f"%{f.location.strip()}%")
        if f.include_remote:
            cond = or_(cond, Job.work_mode == "remote")
        stmt = stmt.where(cond)
    if f.work_mode:
        stmt = stmt.where(Job.work_mode == f.work_mode)
    if f.experience_level:
        stmt = stmt.where(Job.experience_level == f.experience_level)
    return stmt


def _vector_candidates(db: Session, stmt: Select, qvec: list[float]) -> list[tuple[Job, float]]:
    if db.get_bind().dialect.name == "postgresql":
        # pgvector: cosine distance operator (<=>), served by the HNSW index.
        dist = Job.embedding.cosine_distance(qvec)
        rows = db.execute(stmt.add_columns(dist.label("distance")).order_by(dist).limit(CANDIDATES)).all()
        return [(job, 1.0 - float(d)) for job, d in rows]
    # SQLite (unit tests): same maths in Python.
    scored = [(j, _cosine(qvec, j.embedding)) for j in db.scalars(stmt).all() if j.embedding]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:CANDIDATES]


def search_jobs(
    db: Session,
    query: str,
    filters: SearchFilters | None = None,
    mode: str = "hybrid",
    limit: int = 10,
) -> list[SearchHit]:
    filters = filters or SearchFilters()
    w_sem, w_kw = WEIGHTS[mode]
    stmt = _filtered(select(Job), filters)
    tokens = tokenize(query)

    if mode == "keyword":
        # Fine for a small catalogue; at scale use PostgreSQL full-text search.
        pool = [(job, 0.0) for job in db.scalars(stmt).all()]
    else:
        qvec = embeddings.embed_text(query)
        pool = _vector_candidates(db, stmt.where(Job.embedding.is_not(None)), qvec)

    hits = []
    for job, sim in pool:
        sem = min(1.0, max(0.0, sim))
        kw = keyword_score(tokens, job)
        if mode == "keyword" and kw == 0:
            continue
        hits.append(
            SearchHit(
                job=job,
                score=round(w_sem * sem + w_kw * kw, 4),
                semantic_score=round(sem, 4),
                keyword_score=round(kw, 4),
            )
        )
    hits.sort(key=lambda h: (-h.score, h.job.id))
    return hits[:limit]


def profile_query(profile: UserProfile | None) -> str:
    """Turns a user profile into a search query. Empty string if there's nothing to search with."""
    if profile is None or not (profile.skills or profile.target_roles):
        return ""
    parts = []
    if profile.target_roles:
        parts.append("Roles: " + ", ".join(profile.target_roles))
    if profile.skills:
        parts.append("Skills: " + ", ".join(profile.skills))
    if profile.experience_level:
        parts.append(f"Experience level: {profile.experience_level}")
    if profile.summary:
        parts.append(profile.summary)
    return ". ".join(parts)