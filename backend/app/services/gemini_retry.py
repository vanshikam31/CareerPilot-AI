
import logging
import random
import time

logger = logging.getLogger(__name__)

RETRY_MARKERS = (
    "503",
    "UNAVAILABLE",
    "429",
    "RESOURCE_EXHAUSTED",
    "timed out",
    "timeout",
)

def call_with_retry(fn, attempts: int = 4, base_delay: float = 2.0):
    """Retry temporary Gemini API errors with exponential backoff."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()

        except Exception as exc:
            temporary = any(
                marker.lower() in str(exc).lower()
                for marker in RETRY_MARKERS
            )

            if not temporary or attempt == attempts:
                raise

            delay = base_delay * (2 ** (attempt - 1))
            delay += random.uniform(0, 0.5)

            logger.warning(
                "Gemini temporary error (attempt %d/%d). "
                "Retrying in %.2fs",
                attempt,
                attempts,
                delay,
            )

            time.sleep(delay)
