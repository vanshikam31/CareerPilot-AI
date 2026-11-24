from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/api/diagnostics", tags=["system"])


@router.get("/gemini")
def gemini_check(user: User = Depends(get_current_user)):
    info = {"key_set": bool(settings.gemini_api_key), "model": settings.gemini_model}
    if not settings.gemini_api_key:
        return {**info, "ok": False, "error": "GEMINI_API_KEY is empty on this server"}
    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        client.models.generate_content(model=settings.gemini_model, contents="Say hi")
        return {**info, "ok": True}
    except Exception as exc:
        return {**info, "ok": False, "error": str(exc)[:300]}