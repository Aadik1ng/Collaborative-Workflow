"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.db.mongodb import close_mongodb, init_mongodb
from app.db.postgres import close_postgres, init_postgres
from app.db.redis import close_redis, get_redis, init_redis
from app.websocket.routes import router as websocket_router
from app.core.metrics import MetricsMiddleware
from app.services.feature_flags import feature_flags

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting up Collaborative Workspace API...")
    await init_postgres()
    await init_mongodb()
    await init_redis()
    logger.info("All database connections established")

    yield

    # Shutdown
    logger.info("Shutting down Collaborative Workspace API...")
    await close_postgres()
    await close_mongodb()
    await close_redis()
    logger.info("All database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Collaborative Workspace API",
        description="Real-Time Collaborative Workspace Backend for Developers",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)
    
    # Metrics Middleware
    app.add_middleware(MetricsMiddleware)

    # Include API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Include WebSocket router
    app.include_router(websocket_router)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "version": "1.0.0"}

    @app.get("/metrics", tags=["Observability"])
    async def get_metrics() -> dict:
        """Get API metrics from Redis."""
        redis = get_redis()
        counts = await redis.hgetall("metrics:request_counts")
        latencies = await redis.hgetall("metrics:latencies")
        return {
            "request_counts": {k.decode(): int(v) for k, v in counts.items()},
            "latencies_ms": {k.decode(): float(v)*1000 for k, v in latencies.items()}
        }

    @app.get("/api/v1/flags/{name}", tags=["Feature Flags"])
    async def get_flag(name: str):
        """Get feature flag status."""
        return {"flag": name, "enabled": await feature_flags.is_enabled(name)}

    @app.post("/api/v1/flags/{name}", tags=["Feature Flags"])
    async def set_flag(name: str, enabled: bool):
        """Set feature flag status."""
        await feature_flags.set_flag(name, enabled)
        return {"message": f"Flag {name} set to {enabled}"}

    return app


app = create_app()
