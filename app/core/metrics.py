"""Simple metrics collection middleware."""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.redis import get_redis

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect basic API metrics in Redis."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        status_code = response.status_code
        path = request.url.path

        # Record metrics in Redis
        try:
            redis = get_redis()
            # Increment request counter
            await redis.hincrby("metrics:request_counts", f"{path}:{status_code}", 1)
            # Record latency (simplified: just store the latest for the path)
            await redis.hset("metrics:latencies", path, f"{process_time:.4f}")
        except Exception:
            pass # Fail silently for metrics
            
        return response
