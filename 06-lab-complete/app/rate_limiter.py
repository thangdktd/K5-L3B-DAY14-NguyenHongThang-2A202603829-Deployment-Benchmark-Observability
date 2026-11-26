"""
Rate limiting (tiêu chí 7) — sliding window 60s qua Redis sorted set.
"""
import time
import uuid
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    """Giới hạn RATE_LIMIT_PER_MINUTE request / 60s theo API key."""
    now = time.time()
    window_start = now - 60.0
    redis_key = f"rate_limit:{key}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(redis_key, 0, window_start)
    pipe.zcard(redis_key)
    _, count = pipe.execute()

    if count >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    member = f"{now}:{uuid.uuid4().hex}"
    pipe = r.pipeline()
    pipe.zadd(redis_key, {member: now})
    pipe.expire(redis_key, 60)
    pipe.execute()
