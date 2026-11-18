import time

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents.agent import run_agent
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.database.session import get_db
from app.models.conversation import Conversation, Memory, Message
from app.models.user import User
from app.schemas.assistant import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    MemoryOut,
    MessageOut,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _own_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_rate_limit(user.id)
    started = time.perf_counter()

    if req.conversation_id is not None:
        conv = _own_conversation(db, user, req.conversation_id)
    else:
        conv = Conversation(user_id=user.id, title=req.message[:60])
        db.add(conv)
        db.commit()  # saved before the agent runs, so an agent-side rollback cannot lose it
        db.refresh(conv)

    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.desc())
        .limit(settings.agent_history_messages)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(rows)]
    while history and history[0]["role"] != "user":  # the model expects a user message first
        history.pop(0)

    result = run_agent(db, user, history, req.message)
    latency_ms = int((time.perf_counter() - started) * 1000)

    db.add(Message(conversation_id=conv.id, role="user", content=req.message))
    db.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content=result.reply,
            source=result.source,
            tool_calls=result.tool_calls,
            latency_ms=latency_ms,
        )
    )
    db.commit()
    return ChatResponse(
        conversation_id=conv.id,
        reply=result.reply,
        source=result.source,
        tool_calls=result.tool_calls,
        latency_ms=latency_ms,
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id.desc()).limit(50)
    ).all()


@router.get("/conversations/{conversation_id}", response_model=list[MessageOut])
def get_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = _own_conversation(db, user, conversation_id)
    return db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)).all()


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = _own_conversation(db, user, conversation_id)
    db.execute(delete(Message).where(Message.conversation_id == conv.id))
    db.delete(conv)
    db.commit()
    return Response(status_code=204)


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.id)).all()


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memory = db.scalar(select(Memory).where(Memory.id == memory_id, Memory.user_id == user.id))
    if memory is None:
        raise HTTPException(404, "Memory not found")
    db.delete(memory)
    db.commit()
    return Response(status_code=204)