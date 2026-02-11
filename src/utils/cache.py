"""Caching utilities using diskcache."""

import hashlib
import json
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

from diskcache import Cache

from config.settings import get_settings


class CacheManager:
    """Manages caching for the application."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache storage. If None, uses settings.cache_dir.
        """
        settings = get_settings()
        self.cache_dir = cache_dir or settings.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(self.cache_dir))

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        return self.cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time to live in seconds. If None, uses default TTL.
        """
        settings = get_settings()
        expire = ttl or (settings.cache_ttl_hours * 3600)
        self.cache.set(key, value, expire=expire)

    def delete(self, key: str) -> None:
        """
        Delete value from cache.

        Args:
            key: Cache key.
        """
        self.cache.delete(key)

    def clear(self) -> None:
        """Clear all cache."""
        self.cache.clear()

    def close(self) -> None:
        """Close cache connection."""
        self.cache.close()

    @staticmethod
    def generate_key(*args: Any, **kwargs: Any) -> str:
        """
        Generate cache key from arguments.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Cache key as hex string.
        """
        # Create a consistent string representation
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items()),
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds. If None, uses default TTL.
        key_prefix: Prefix for cache key.

    Returns:
        Decorated function with caching.

    Example:
        @cached(ttl=3600, key_prefix="user_profile")
        def get_user_profile(user_id: str):
            # Expensive operation
            return profile
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_manager = get_cache_manager()

            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{CacheManager.generate_key(*args, **kwargs)}"

            # Try to get from cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Compute value
            result = func(*args, **kwargs)

            # Store in cache
            cache_manager.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator
