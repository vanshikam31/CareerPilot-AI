"""Tiny in-memory sliding-window limiter. Per process only: with several servers
you would move this to Redis."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[int, deque] = defaultdict(deque)


def check_rate_limit(user_id: int, limit: int = 15, window_seconds: int = 60) -> None:
    now = time.monotonic()
    q = _hits[user_id]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests. Please wait a minute.")
    q.append(now)


def reset() -> None:
    _hits.clear()