"""MongoDB database connection and client management."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

# Global MongoDB client and database
mongodb_client: AsyncIOMotorClient | None = None
mongodb_database: AsyncIOMotorDatabase | None = None


async def init_mongodb() -> None:
    """Initialize MongoDB connection."""
    global mongodb_client, mongodb_database

    mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
    mongodb_database = mongodb_client[settings.MONGODB_DATABASE]

    # Try to create indexes, but don't fail startup if it errors
    try:
        await _create_indexes()
    except Exception as e:
        import logging
        logging.warning(f"Could not create MongoDB indexes (non-fatal): {e}")


async def _create_indexes() -> None:
    """Create MongoDB indexes for optimal query performance."""
    if mongodb_database is None:
        return

    # Activities collection indexes
    activities = mongodb_database.activities
    await activities.create_index([("project_id", 1), ("timestamp", -1)])
    await activities.create_index([("workspace_id", 1), ("timestamp", -1)])
    await activities.create_index([("user_id", 1), ("timestamp", -1)])
    # TTL index - expire after 7 days
    await activities.create_index([("timestamp", 1)], expireAfterSeconds=604800)

    # Job results collection indexes
    job_results = mongodb_database.job_results
    await job_results.create_index([("user_id", 1), ("created_at", -1)])
    await job_results.create_index([("status", 1)])


async def close_mongodb() -> None:
    """Close MongoDB connection."""
    global mongodb_client

    if mongodb_client:
        mongodb_client.close()


def get_mongodb() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance."""
    if mongodb_database is None:
        raise RuntimeError("MongoDB is not initialized")
    return mongodb_database


def get_activities_collection():
    """Get activities collection."""
    return get_mongodb().activities


def get_job_results_collection():
    """Get job results collection."""
    return get_mongodb().job_results
