"""Used when Gemini is unavailable. No LLM: just local hybrid search, formatted as text."""
from sqlalchemy.orm import Session

from app.agents.types import AgentResult
from app.models.user import User
from app.retrieval.search import profile_query, search_jobs, tokenize

NOTICE = "The AI assistant is unavailable right now, so these are the best matches from job search."
HELP = (
    "The AI assistant is unavailable right now. Tell me a role or skills "
    "(for example 'python backend jobs') and I will search for you."
)


def fallback_reply(db: Session, user: User, message: str) -> AgentResult:
    query = message if tokenize(message) else profile_query(user.profile)
    if not query:
        return AgentResult(HELP, "fallback", [])

    try:
        hits = search_jobs(db, query, mode="hybrid", limit=5)
    except Exception:  # e.g. embedding model unavailable: keyword search still works
        hits = search_jobs(db, query, mode="keyword", limit=5)

    trace = [{"name": "search_jobs", "args": {"query": query[:200]}, "ok": True}]
    if not hits:
        return AgentResult("No matching jobs found. Try different keywords.", "fallback", trace)

    lines = [NOTICE, ""]
    for i, h in enumerate(hits, start=1):
        j = h.job
        lines.append(
            f"{i}. **{j.title}** at {j.company} ({j.location}, {j.work_mode}) [job #{j.id}]. "
            f"Skills: {', '.join(j.skills[:5])}"
        )
    return AgentResult("\n".join(lines), "fallback", trace)