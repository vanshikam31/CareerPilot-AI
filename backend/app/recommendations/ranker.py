"""Personalised ranking. Pure functions: no database, no network, so they are easy to test."""
from dataclasses import dataclass

from app.retrieval.search import tokenize

LEVEL_ORDER = {"fresher": 0, "junior": 1, "mid": 2, "senior": 3}
LEVEL_SCORES = {0: 1.0, 1: 0.5, 2: 0.15}  # distance between user level and job level
NEUTRAL = 0.5  # used when the user has not told us something

# Heuristic weights (sum = 1.0). Not tuned on data yet.
WEIGHTS = {"semantic": 0.35, "skills": 0.30, "role": 0.15, "level": 0.10, "location": 0.10}

# Words that appear in many titles and say little about the role.
GENERIC_TITLE_WORDS = {"engineer", "developer", "senior", "junior", "associate", "software"}


@dataclass
class UserSignals:
    skills: list[str]
    target_roles: list[str]
    preferred_locations: list[str]
    experience_level: str | None


@dataclass
class Recommendation:
    job: object
    score: float
    breakdown: dict
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str]


def normalise(values: list[float]) -> list[float]:
    """Min-max scale to 0..1. Raw cosine scores sit in a narrow band, so we compare within the pool."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [NEUTRAL] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def skill_match(user_skills: list[str], job_skills: list[str]) -> tuple[float, list[str], list[str]]:
    mine = {s.lower() for s in user_skills}
    required = list(job_skills or [])
    if not required:
        return 0.0, [], []
    matched = [s for s in required if s.lower() in mine]
    missing = [s for s in required if s.lower() not in mine]
    return len(matched) / len(required), matched, missing


def level_fit(user_level: str | None, job_level: str | None) -> float:
    if user_level not in LEVEL_ORDER or job_level not in LEVEL_ORDER:
        return NEUTRAL
    return LEVEL_SCORES.get(abs(LEVEL_ORDER[user_level] - LEVEL_ORDER[job_level]), 0.0)


def location_fit(preferred: list[str], job) -> float:
    if not preferred:
        return NEUTRAL
    if job.work_mode == "remote":
        return 1.0
    loc = job.location.lower()
    for place in preferred:
        place = place.strip().lower()
        if place and (place in loc or loc in place):
            return 1.0
    return 0.0


def role_fit(target_roles: list[str], title: str) -> float:
    if not target_roles:
        return NEUTRAL
    title_lower = title.lower()
    title_tokens = set(tokenize(title))
    best = 0.0
    for role in target_roles:
        role_lower = role.strip().lower()
        if not role_lower:
            continue
        if role_lower in title_lower:
            return 1.0
        tokens = set(tokenize(role))
        tokens = (tokens - GENERIC_TITLE_WORDS) or tokens
        if tokens:
            best = max(best, len(tokens & title_tokens) / len(tokens))
    return best


def _explain(user: UserSignals, job, parts: dict, matched: list[str], missing: list[str]) -> list[str]:
    reasons = []
    total = len(matched) + len(missing)
    if total:
        if matched:
            reasons.append(f"You already have {len(matched)} of {total} required skills: {', '.join(matched[:6])}.")
        else:
            reasons.append(f"You have none of the {total} required skills yet.")
        if missing:
            reasons.append(f"Skills to learn: {', '.join(missing[:6])}.")
    if user.target_roles:
        if parts["role"] >= 1.0:
            reasons.append("Job title matches your target role.")
        elif parts["role"] > 0:
            reasons.append("Job title partly matches your target roles.")
    if user.experience_level in LEVEL_ORDER:
        if job.experience_level == user.experience_level:
            reasons.append(f"Experience level fits ({job.experience_level}).")
        elif parts["level"] <= 0.15:
            reasons.append(f"This is a {job.experience_level}-level role, far from your {user.experience_level} level.")
    if user.preferred_locations:
        if job.work_mode == "remote":
            reasons.append("Remote role, so location is not a problem.")
        elif parts["location"] >= 1.0:
            reasons.append(f"Located in {job.location}, one of your preferred locations.")
        else:
            reasons.append(f"Located in {job.location}, outside your preferred locations.")
    return reasons


def rank_jobs(user: UserSignals, candidates: list[tuple[object, float]], limit: int = 10) -> list[Recommendation]:
    """candidates: (job, raw semantic similarity). Returns the best `limit`, highest score first."""
    semantic = normalise([sim for _, sim in candidates])
    ranked = []
    for (job, _), sem in zip(candidates, semantic):
        skills, matched, missing = skill_match(user.skills, job.skills)
        parts = {
            "semantic": sem,
            "skills": skills,
            "role": role_fit(user.target_roles, job.title),
            "level": level_fit(user.experience_level, job.experience_level),
            "location": location_fit(user.preferred_locations, job),
        }
        score = sum(WEIGHTS[name] * value for name, value in parts.items())
        ranked.append(
            Recommendation(
                job=job,
                score=round(score, 4),
                breakdown={name: round(value, 3) for name, value in parts.items()},
                matched_skills=matched,
                missing_skills=missing,
                reasons=_explain(user, job, parts, matched, missing),
            )
        )
    ranked.sort(key=lambda r: (-r.score, r.job.id))
    return ranked[:limit]