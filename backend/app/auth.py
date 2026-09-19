"""Telegram auth validation + tiny in-memory rate limiter."""
import hashlib
import hmac
import time
from collections import defaultdict, deque
from urllib.parse import parse_qsl

from fastapi import HTTPException


def validate_telegram_init_data(init_data: str, bot_token: str = "") -> bool:
    """Validate Telegram WebApp initData per official docs.

    Returns True when no bot token is configured (demo leniency) or when
    the HMAC-SHA256 signature checks out. Never raises for missing data —
    callers decide whether auth is mandatory.
    """
    if not init_data or not bot_token:
        return True
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(calc, received_hash)
    except Exception:
        return False


class RateLimiter:
    """Sliding-window limiter keyed by user id (process-local, MVP-grade)."""

    def __init__(self, max_hits: int, window_sec: int):
        self.max_hits = max_hits
        self.window = window_sec
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.max_hits:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Slow down.")
        hits.append(now)


_limiter: RateLimiter | None = None


def get_limiter(max_hits: int, window_sec: int) -> RateLimiter:
    global _limiter
    if _limiter is None or _limiter.max_hits != max_hits or _limiter.window != window_sec:
        _limiter = RateLimiter(max_hits, window_sec)
    return _limiter
