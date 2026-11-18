"""Metrics computed from the agent's own saved conversations (messages table)."""
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message
from app.models.job import Job

CITATION_RE = re.compile(r"\[job\s*#\s*(\d+)\]", re.IGNORECASE)
COST_NOTE = "Gemini free tier: cost is $0. Token usage is not logged yet."


def extract_citations(reply: str) -> list[int]:
    return list(dict.fromkeys(int(n) for n in CITATION_RE.findall(reply)))


def citation_report(reply: str, seen_ids: set[int], jobs: dict[int, tuple[str, str]]) -> dict:
    """grounded: the cited job was really returned by a tool in this turn.
    consistent: the line with the citation also names that job's company or title."""
    cited = extract_citations(reply)
    grounded = sum(1 for i in cited if i in seen_ids)
    checked = consistent = 0
    lines = reply.splitlines()
    for job_id in cited:
        if job_id not in jobs:
            continue
        checked += 1
        title, company = jobs[job_id]
        pattern = re.compile(rf"\[job\s*#\s*{job_id}\]", re.IGNORECASE)
        line = next((ln for ln in lines if pattern.search(ln)), "").lower()
        if company.lower() in line or title.lower() in line:
            consistent += 1
    return {"cited": len(cited), "grounded": grounded, "checked": checked, "consistent": consistent}


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _percentile(sorted_values: list[int], p: int) -> int | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, math.ceil(p / 100 * len(sorted_values)) - 1))
    return sorted_values[index]


def compute_agent_metrics(db: Session, user_id: int) -> dict:
    messages = db.scalars(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user_id, Message.role == "assistant")
    ).all()

    gemini = [m for m in messages if m.source == "gemini"]
    all_calls = [c for m in messages for c in (m.tool_calls or [])]
    latencies = sorted(m.latency_ms for m in messages if m.latency_ms is not None)

    # Only replies saved after Phase 5 carry "job_ids" in their trace; older ones can't be checked.
    checkable = [m for m in gemini if not any("job_ids" not in c for c in (m.tool_calls or []))]
    cited_ids = {i for m in checkable for i in extract_citations(m.content)}
    jobs: dict[int, tuple[str, str]] = {}
    if cited_ids:
        rows = db.execute(select(Job.id, Job.title, Job.company).where(Job.id.in_(cited_ids)))
        jobs = {job_id: (title, company) for job_id, title, company in rows}

    totals = {"cited": 0, "grounded": 0, "checked": 0, "consistent": 0}
    for m in checkable:
        seen = {i for c in (m.tool_calls or []) for i in c.get("job_ids", [])}
        report = citation_report(m.content, seen, jobs)
        for key in totals:
            totals[key] += report[key]

    return {
        "replies": len(messages),
        "gemini_replies": len(gemini),
        "fallback_replies": len(messages) - len(gemini),
        "fallback_rate": _rate(len(messages) - len(gemini), len(messages)),
        "tool_calls": len(all_calls),
        "tool_call_success_rate": _rate(sum(1 for c in all_calls if c.get("ok")), len(all_calls)),
        "avg_tool_calls_per_reply": round(len(all_calls) / len(messages), 2) if messages else None,
        "latency_avg_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "latency_p95_ms": _percentile(latencies, 95),
        "citations_total": totals["cited"],
        "citation_grounding_rate": _rate(totals["grounded"], totals["cited"]),
        "citation_consistency_rate": _rate(totals["consistent"], totals["checked"]),
        "cost_note": COST_NOTE,
    }