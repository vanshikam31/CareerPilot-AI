from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class Turn:
    """One model response: either final text, or a list of tool calls."""
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    raw: object = None  # provider-specific message, kept so it can be sent back


@dataclass
class AgentResult:
    reply: str
    source: str  # gemini | fallback
    tool_calls: list[dict]