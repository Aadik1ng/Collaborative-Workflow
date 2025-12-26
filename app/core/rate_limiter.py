"""Rate limiting middleware using Redis sliding window."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based sliding window rate limiting middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health check
        if request.url.path == "/health":
            return await call_next(request)

        # Get client identifier (IP or user ID from token)
        client_id = self._get_client_id(request)

        # Check rate limit
        is_allowed, remaining, reset_time = await self._check_rate_limit(client_id)

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": reset_time,
                },
                headers={
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID from authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Use token hash as identifier (more granular per-user limiting)
            return f"user:{hash(auth_header)}"

        # Fall back to client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    async def _check_rate_limit(
        self, client_id: str
    ) -> tuple[bool, int, int]:
        """Check rate limit using Redis sliding window.

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_time_seconds)
        """
        try:
            from app.db.redis import get_redis

            redis = get_redis()
            key = f"ratelimit:{client_id}"
            current_time = int(time.time())
            window_start = current_time - settings.RATE_LIMIT_WINDOW

            # Use Redis transaction for atomic operations
            pipe = redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiry on the key
            pipe.expire(key, settings.RATE_LIMIT_WINDOW)

            results = await pipe.execute()
            request_count = results[1]

            remaining = max(0, settings.RATE_LIMIT_REQUESTS - request_count - 1)
            reset_time = settings.RATE_LIMIT_WINDOW

            if request_count >= settings.RATE_LIMIT_REQUESTS:
                # Remove the request we just added since it's over limit
                await redis.zrem(key, str(current_time))
                return False, 0, reset_time

            return True, remaining, reset_time

        except Exception:
            # If Redis is unavailable, allow the request (fail open)
            return True, settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW
