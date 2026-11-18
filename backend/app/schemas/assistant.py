from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class ToolCallOut(BaseModel):
    name: str
    args: dict
    ok: bool


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    source: str  # gemini | fallback
    tool_calls: list[ToolCallOut]
    latency_ms: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    source: str | None
    tool_calls: list[dict]
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    created_at: datetime


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    content: str
    created_at: datetime