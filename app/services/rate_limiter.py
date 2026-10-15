import time
from collections import defaultdict, deque

from app.core.config import settings


class InMemoryRateLimiter:
    """Simple per-key sliding-window rate limiter stored in memory.

    Suitable for a single-process uvicorn deployment. For multi-worker
    deployments a shared store (Redis, etc.) would be required.
    """

    def __init__(self, max_requests: int = None, window_seconds: int = None):
        self.max_requests = max_requests or settings.RATE_LIMIT_MAX
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self._hits: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> None:
        window_start = now - self.window_seconds
        while self._hits[key] and self._hits[key][0] < window_start:
            self._hits[key].popleft()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        self._prune(key, now)
        if len(self._hits[key]) >= self.max_requests:
            return False
        self._hits[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        self._prune(key, now)
        return max(0, self.max_requests - len(self._hits[key]))


rate_limiter = InMemoryRateLimiter()


def client_key(request) -> str:
    """Build a rate-limit key from the client IP.

    Returns None when there is no real client IP (e.g. in-process test
    clients via ASGITransport), in which case rate limiting is skipped.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    if request.client and request.client.host:
        return request.client.host
    return None