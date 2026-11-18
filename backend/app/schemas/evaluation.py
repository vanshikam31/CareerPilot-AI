from pydantic import BaseModel


class AgentMetricsOut(BaseModel):
    replies: int
    gemini_replies: int
    fallback_replies: int
    fallback_rate: float | None
    tool_calls: int
    tool_call_success_rate: float | None
    avg_tool_calls_per_reply: float | None
    latency_avg_ms: int | None
    latency_p95_ms: int | None
    citations_total: int
    citation_grounding_rate: float | None
    citation_consistency_rate: float | None
    cost_note: str