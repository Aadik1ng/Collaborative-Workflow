"""Feature flag service."""

from app.db.redis import cache_get, cache_set


class FeatureFlagService:
    """Simple feature flag service using Redis."""

    def __init__(self):
        # Default flags
        self._defaults = {
            "enable_code_execution": True,
            "enable_rate_limiting": True,
            "maintenance_mode": False,
        }

    async def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        val = await cache_get(f"feature_flag:{flag_name}")
        if val is None:
            return self._defaults.get(flag_name, False)
        return str(val).lower() == "true"

    async def set_flag(self, flag_name: str, enabled: bool):
        """Set a feature flag value."""
        await cache_set(f"feature_flag:{flag_name}", str(enabled).lower())


feature_flags = FeatureFlagService()
