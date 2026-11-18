from collections import Counter

from sqlalchemy.orm import Session

from app.models.user import User, UserProfile
from app.recommendations.ranker import Recommendation, UserSignals, rank_jobs
from app.retrieval.search import SearchFilters, profile_query, search_jobs

CANDIDATE_POOL = 50


class NoProfileError(ValueError):
    pass


def signals_from_profile(profile: UserProfile | None) -> UserSignals:
    if profile is None:
        return UserSignals([], [], [], None)
    return UserSignals(
        skills=list(profile.skills or []),
        target_roles=list(profile.target_roles or []),
        preferred_locations=list(profile.preferred_locations or []),
        experience_level=profile.experience_level,
    )


def recommend(
    db: Session, profile: UserProfile | None, location: str | None = None, limit: int = 10
) -> list[Recommendation]:
    """Stage 1: vector search gets 50 candidates. Stage 2: the ranker scores them."""
    query = profile_query(profile)
    if not query:
        raise NoProfileError("Add skills or target roles to your profile, or upload a resume first")
    hits = search_jobs(db, query, SearchFilters(location=location), mode="semantic", limit=CANDIDATE_POOL)
    return rank_jobs(signals_from_profile(profile), [(h.job, h.semantic_score) for h in hits], limit=limit)


def recommend_for_user(db: Session, user: User, location: str | None = None, limit: int = 10) -> list[Recommendation]:
    return recommend(db, user.profile, location=location, limit=limit)


def learning_path(recs: list[Recommendation]) -> list[dict]:
    """Missing skills across the recommended jobs; the most demanded skill comes first."""
    counts: Counter = Counter()
    for rec in recs:
        counts.update(rec.missing_skills)
    total = len(recs) or 1
    return [
        {"skill": skill, "jobs_needing_it": n, "percent_of_top_jobs": round(100 * n / total)}
        for skill, n in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]