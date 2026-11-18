import logging
import threading
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Stored inside backend/ (not the OS temp folder, which Windows may clean up).
CACHE_DIR = Path(__file__).resolve().parents[2] / ".model_cache"

_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    with _lock:
        if _model is None:
            # Imported lazily so the app and the tests start fast.
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=settings.embedding_model, cache_dir=str(CACHE_DIR))
        return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return [vec.tolist() for vec in _get_model().embed(texts)]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def warmup() -> None:
    try:
        embed_text("warm up")
        logger.info("Embedding model ready: %s", settings.embedding_model)
    except Exception as exc:
        logger.warning("Embedding warm-up failed: %s", exc)