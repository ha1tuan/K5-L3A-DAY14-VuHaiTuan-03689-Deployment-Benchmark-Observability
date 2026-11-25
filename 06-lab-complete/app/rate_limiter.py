"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException

from app import redis_client
from app.config import settings

WINDOW_SECONDS = 60
_memory_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    now = time.time()
    window_start = now - WINDOW_SECONDS
    limit = settings.rate_limit_per_minute

    if redis_client.r is not None:
        redis_key = f"ratelimit:{key}"
        try:
            pipe = redis_client.r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            _, count = pipe.execute()

            if count >= limit:
                oldest = redis_client.r.zrange(redis_key, 0, 0, withscores=True)
                retry_after = (
                    max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
                    if oldest
                    else WINDOW_SECONDS
                )
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            member = f"{now}:{uuid.uuid4().hex[:8]}"
            pipe = redis_client.r.pipeline()
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, WINDOW_SECONDS + 5)
            pipe.execute()
            return
        except HTTPException:
            raise
        except Exception:
            pass

    # Fallback in-memory khi Redis chưa sẵn sàng
    window = _memory_windows[key]
    while window and window[0] < window_start:
        window.popleft()
    if len(window) >= limit:
        retry_after = max(1, int(window[0] + WINDOW_SECONDS - now) + 1)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    window.append(now)
