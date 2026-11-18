"""The agent's tools. Each tool validates its arguments and returns plain JSON-safe data.
Errors are returned to the model as {"error": ...} so it can recover."""
import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.conversation import Memory
from app.models.job import Job
from app.models.user import User
from app.retrieval.search import SearchFilters, search_jobs

logger = logging.getLogger(__name__)

WORK_MODES = ("onsite", "hybrid", "remote")
LEVELS = ("fresher", "junior", "mid", "senior")
MAX_MEMORIES = 50


class ToolError(ValueError):
    pass


@dataclass
class ToolContext:
    db: Session
    user: User


TOOL_SPECS = [
    {
        "name": "search_jobs",
        "description": "Search the job database by meaning and keywords. Returns the best matching jobs with ids.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for, e.g. 'python backend apis'."},
                "location": {"type": "string", "description": "City name, e.g. 'Gurgaon'. Remote jobs are included too."},
                "work_mode": {"type": "string", "enum": list(WORK_MODES)},
                "experience_level": {"type": "string", "enum": list(LEVELS)},
                "limit": {"type": "integer", "description": "Number of results, 1 to 10. Default 5."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_job_details",
        "description": "Get the full description and skills of one job by its id.",
        "parameters": {
            "type": "object",
            "properties": {"job_id": {"type": "integer"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "get_my_profile",
        "description": "Get the current user's profile: skills, target roles, locations, experience level.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "skill_gap",
        "description": "Compare the user's skills with one job's required skills (matched and missing).",
        "parameters": {
            "type": "object",
            "properties": {"job_id": {"type": "integer"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "save_preference",
        "description": "Remember a lasting user preference (preferred city, role, work mode, goals) for future chats.",
        "parameters": {
            "type": "object",
            "properties": {"fact": {"type": "string", "description": "One short sentence, max 300 characters."}},
            "required": ["fact"],
        },
    },
]


def _int(args: dict, key: str, default: int | None = None, lo: int = 1, hi: int = 10**9) -> int:
    value = args.get(key, default)
    if value is None:
        raise ToolError(f"'{key}' is required")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ToolError(f"'{key}' must be an integer")
    return max(lo, min(hi, value))


def _opt_str(args: dict, key: str, allowed: tuple | None = None) -> str | None:
    value = args.get(key)
    if value in (None, ""):
        return None
    value = str(value).strip()
    if allowed and value.lower() not in allowed:
        raise ToolError(f"'{key}' must be one of {list(allowed)}")
    return value.lower() if allowed else value


def _get_job(ctx: ToolContext, args: dict) -> Job:
    job = ctx.db.get(Job, _int(args, "job_id"))
    if job is None:
        raise ToolError("job not found")
    return job


def _search_jobs(ctx: ToolContext, args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    if len(query) < 2:
        raise ToolError("'query' is required")
    filters = SearchFilters(
        location=_opt_str(args, "location"),
        work_mode=_opt_str(args, "work_mode", WORK_MODES),
        experience_level=_opt_str(args, "experience_level", LEVELS),
    )
    hits = search_jobs(ctx.db, query[:500], filters, mode="hybrid", limit=_int(args, "limit", 5, 1, 10))
    return {
        "count": len(hits),
        "jobs": [
            {
                "id": h.job.id,
                "title": h.job.title,
                "company": h.job.company,
                "location": h.job.location,
                "work_mode": h.job.work_mode,
                "experience_level": h.job.experience_level,
                "skills": h.job.skills,
                "match_score": h.score,
                "summary": h.job.description[:300],
            }
            for h in hits
        ],
    }


def _get_job_details(ctx: ToolContext, args: dict) -> dict:
    job = _get_job(ctx, args)
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_mode": job.work_mode,
        "experience_level": job.experience_level,
        "category": job.category,
        "skills": job.skills,
        "description": job.description[:1500],
    }


def _get_my_profile(ctx: ToolContext, args: dict) -> dict:
    p = ctx.user.profile
    if p is None:
        return {"skills": [], "target_roles": [], "preferred_locations": []}
    return {
        "name": ctx.user.full_name,
        "skills": p.skills or [],
        "target_roles": p.target_roles or [],
        "preferred_locations": p.preferred_locations or [],
        "experience_level": p.experience_level,
        "education": p.education,
        "summary": p.summary,
    }


def _skill_gap(ctx: ToolContext, args: dict) -> dict:
    job = _get_job(ctx, args)
    mine = {s.lower() for s in (ctx.user.profile.skills if ctx.user.profile else [])}
    required = job.skills or []
    matched = [s for s in required if s.lower() in mine]
    missing = [s for s in required if s.lower() not in mine]
    return {
        "job_id": job.id,
        "job_title": job.title,
        "matched": matched,
        "missing": missing,
        "match_percent": round(100 * len(matched) / len(required)) if required else 0,
    }


def _save_preference(ctx: ToolContext, args: dict) -> dict:
    fact = " ".join(str(args.get("fact", "")).split())[:300]
    if len(fact) < 3:
        raise ToolError("'fact' is required")
    db, uid = ctx.db, ctx.user.id
    existing = db.scalars(select(Memory.content).where(Memory.user_id == uid)).all()
    if fact.lower() in {m.lower() for m in existing}:
        return {"saved": False, "reason": "already remembered"}
    if len(existing) >= MAX_MEMORIES:
        raise ToolError("memory is full; ask the user to delete some memories")
    db.add(Memory(user_id=uid, content=fact))
    db.commit()
    return {"saved": True}


_TOOLS = {
    "search_jobs": _search_jobs,
    "get_job_details": _get_job_details,
    "get_my_profile": _get_my_profile,
    "skill_gap": _skill_gap,
    "save_preference": _save_preference,
}


def run_tool(ctx: ToolContext, name: str, args: dict | None) -> tuple[dict, bool]:
    """Returns (result, ok). Never raises."""
    fn = _TOOLS.get(name)
    if fn is None:
        return {"error": f"unknown tool '{name}'"}, False
    try:
        return fn(ctx, args or {}), True
    except ToolError as exc:
        return {"error": str(exc)}, False
    except Exception:
        logger.exception("Tool %s crashed", name)
        ctx.db.rollback()
        return {"error": "tool failed"}, False