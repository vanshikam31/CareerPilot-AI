import logging
import time

logger = logging.getLogger(__name__)

RETRY_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "timed out", "timeout")


def call_with_retry(fn, attempts: int = 3, base_delay: float = 1.5):
    """Calls fn(). Retries only on temporary errors (overload, rate limit, timeout)."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            temporary = any(m.lower() in str(exc).lower() for m in RETRY_MARKERS)
            if not temporary or attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))  # 1.5s, 3s
            logger.warning("Gemini temporary error (attempt %d/%d), retrying in %.1fs", attempt, attempts, delay)
            time.sleep(delay)