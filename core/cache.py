"""
Caching System for the Profile API.

This module provides a flexible and extensible caching system designed to improve
the performance and resilience of the Profile API. It features an abstract
`CacheBackend` and a high-level `CacheManager` to orchestrate caching operations.

Key Components:
- CacheBackend (ABC): An abstract base class that defines the standard interface
  for all cache implementations. This allows for different caching strategies
  (e.g., in-memory, Redis) to be used interchangeably.
- MemoryCacheBackend: An in-memory cache implementation that uses a dictionary for
  storage and a Least Recently Used (LRU) eviction policy. It is suitable for
  single-instance deployments and development environments.
- RedisCacheBackend: A placeholder for a Redis-based cache backend, intended for
  use in distributed, production environments. (Not fully implemented).
- CacheManager: A high-level facade that provides a simple and consistent API for
  interacting with the configured cache backend. It handles common caching
  patterns like "get-or-set" and pattern-based invalidation.
- Decorators (`@cached`): Provides a convenient way to apply caching to functions,
  reducing boilerplate code and separating caching logic from business logic.

Architectural Design:
- Strategy Pattern: The use of `CacheBackend` as an abstract base class is an
  example of the Strategy pattern. It allows the caching algorithm/storage to be
  selected at runtime without changing the client code (i.e., `CacheManager`).
- Facade Pattern: `CacheManager` acts as a facade, simplifying the interface to
  the more complex underlying cache backends.
- Singleton Pattern (via `get_cache_manager`): A single, global instance of the
  `CacheManager` is used throughout the application to ensure a consistent
  caching state.
- Asynchronous by Design: All caching operations are asynchronous (`async`/`await`)
  to ensure they do not block the event loop, which is critical for a high-
  performance FastAPI application.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from functools import wraps
import sys

from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0

    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
        if self.size_bytes == 0:
            self.size_bytes = sys.getsizeof(self.value)

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class CacheBackend(ABC):
    """Abstract base class for cache backends"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get cache entry value by key"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cache entry with optional TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cache entry"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries"""
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get cache keys matching pattern"""
        pass

    @abstractmethod
    async def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        pass


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend with LRU eviction"""

    def __init__(
        self, max_size: int = 1000, max_memory_mb: int = 100, default_ttl: int = 300
    ):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []  # For LRU tracking
        self.total_size_bytes = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self.cache:
                self.misses += 1
                logger.debug(f"Cache miss for key: {key}")
                return None

            entry = self.cache[key]

            # Check if expired
            if entry.is_expired:
                await self._remove_key(key)
                self.misses += 1
                logger.debug(f"Cache expired for key: {key}")
                return None

            # Update access tracking
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()

            # Move to end of access order (most recently used)
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            self.hits += 1
            logger.debug(f"Cache hit for key: {key}")
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        async with self._lock:
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)

            entry = CacheEntry(
                value=value, created_at=datetime.utcnow(), expires_at=expires_at
            )

            # Check if we need to evict
            await self._ensure_capacity(entry.size_bytes)

            # Remove existing entry if present
            if key in self.cache:
                await self._remove_key(key)

            # Add new entry
            self.cache[key] = entry
            self.access_order.append(key)
            self.total_size_bytes += entry.size_bytes

            logger.debug(f"Cache set for key: {key}, TTL: {ttl}")
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self.cache:
                await self._remove_key(key)
                logger.debug(f"Cache deleted for key: {key}")
                return True
            return False

    async def clear(self) -> bool:
        async with self._lock:
            self.cache.clear()
            self.access_order.clear()
            self.total_size_bytes = 0
            logger.info("Cache cleared")
            return True

    async def keys(self, pattern: str = "*") -> List[str]:
        async with self._lock:
            if pattern == "*":
                return list(self.cache.keys())

            # Simple pattern matching (could be enhanced)
            import fnmatch

            return [key for key in self.cache.keys() if fnmatch.fnmatch(key, pattern)]

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        async with self._lock:
            if key not in self.cache:
                return False

            entry = self.cache[key]
            if entry.is_expired:
                await self.delete(key)
                return False

            return True

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        async with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

            return {
                "backend": "memory",
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "evictions": self.evictions,
                "entries": len(self.cache),
                "max_size": self.max_size,
                "memory_usage_bytes": sum(
                    entry.size_bytes for entry in self.cache.values()
                ),
            }

    async def stats(self) -> Dict[str, Any]:
        async with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests) if total_requests > 0 else 0

            return {
                "backend": "memory",
                "total_keys": len(self.cache),
                "max_size": self.max_size,
                "memory_usage_bytes": self.total_size_bytes,
                "max_memory_bytes": self.max_memory_bytes,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "evictions": self.evictions,
            }

    async def _remove_key(self, key: str) -> None:
        """Remove key from cache and update tracking"""
        if key in self.cache:
            entry = self.cache[key]
            self.total_size_bytes -= entry.size_bytes
            del self.cache[key]

            if key in self.access_order:
                self.access_order.remove(key)

    async def _ensure_capacity(self, new_entry_size: int) -> None:
        """Ensure cache has capacity for new entry"""
        # Check size limit
        while (
            len(self.cache) >= self.max_size
            or self.total_size_bytes + new_entry_size > self.max_memory_bytes
        ):
            if not self.access_order:
                break

            # Evict least recently used
            lru_key = self.access_order[0]
            await self._remove_key(lru_key)
            self.evictions += 1
            logger.debug(f"Evicted LRU key: {lru_key}")


class RedisCacheBackend(CacheBackend):
    """Redis cache backend implementation (placeholder)"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis = None  # Would be initialized with actual Redis client

    async def get(self, key: str) -> Optional[Any]:
        """Get cache entry value by key"""
        # Abstract implementation - would use Redis client
        raise NotImplementedError("Redis backend not implemented yet")

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cache entry with optional TTL"""
        # Abstract implementation - would use Redis client
        raise NotImplementedError("Redis backend not implemented yet")

    async def delete(self, key: str) -> bool:
        """Delete cache entry"""
        # Abstract implementation - would use Redis client
        raise NotImplementedError("Redis backend not implemented yet")

    async def clear(self) -> bool:
        """Clear all cache entries"""
        # Abstract implementation - would use Redis client
        raise NotImplementedError("Redis backend not implemented yet")

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get cache keys matching pattern"""
        # Abstract implementation - would use Redis client
        raise NotImplementedError("Redis backend not implemented yet")

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        # Abstract implementation - would use Redis client
        raise NotImplementedError("Redis backend not implemented yet")

    async def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        # Abstract implementation - would use Redis client
        return {"backend": "redis", "status": "not_implemented"}


class CacheManager:
    """High-level cache manager"""

    def __init__(self, backend: CacheBackend):
        self.backend = backend
        self.logger = get_logger(f"{__name__}.CacheManager")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            return await self.backend.get(key)
        except Exception as e:
            self.logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            return await self.backend.set(key, value, ttl)
        except Exception as e:
            self.logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            return await self.backend.delete(key)
        except Exception as e:
            self.logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def get_or_set(self, key: str, factory, ttl: Optional[int] = None) -> Any:
        """Get value from cache or set it using factory function"""
        value = await self.get(key)
        if value is not None:
            return value

        # Generate value using factory
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern"""
        try:
            keys = await self.backend.keys(pattern)
            count = 0
            for key in keys:
                if await self.backend.delete(key):
                    count += 1
            self.logger.info(f"Invalidated {count} keys matching pattern: {pattern}")
            return count
        except Exception as e:
            self.logger.error(f"Cache invalidation error for pattern {pattern}: {e}")
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        try:
            test_key = "__health_check__"
            test_value = "ok"

            # Test set
            await self.set(test_key, test_value, ttl=1)

            # Test get
            retrieved = await self.get(test_key)

            # Test delete
            await self.delete(test_key)

            # Get stats
            stats = await self.backend.stats()

            return {
                "status": "healthy" if retrieved == test_value else "unhealthy",
                "backend_type": stats.get("backend", "unknown"),
                "stats": stats,
            }
        except Exception as e:
            self.logger.error(f"Cache health check failed: {e}")
            return {"status": "unhealthy", "backend_type": "unknown", "error": str(e)}


# Cache decorators
def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """Decorator to cache function results"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            if args:
                key_parts.extend(str(arg) for arg in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(filter(None, key_parts))

            # Try to get from cache (assumes cache_manager is available)
            if hasattr(func, "_cache_manager"):
                cache_manager = func._cache_manager
                cached_result = await cache_manager.get(cache_key)
                if cached_result is not None:
                    return cached_result

            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Store in cache
            if hasattr(func, "_cache_manager"):
                await cache_manager.set(cache_key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't use async cache operations
            # This is a simplified version
            return func(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def cache_key(*key_parts) -> str:
    """Generate a cache key from parts"""
    return ":".join(str(part) for part in key_parts if part is not None)


# Global cache manager instance
cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global cache_manager
    if cache_manager is None:
        # Initialize with memory backend by default
        backend = MemoryCacheBackend()
        cache_manager = CacheManager(backend)
    return cache_manager


def get_cache() -> CacheManager:
    """Alias for get_cache_manager for backward compatibility."""
    return get_cache_manager()


def init_cache(backend: CacheBackend = None) -> CacheManager:
    """Initialize the global cache manager with a specific backend."""
    global cache_manager
    if backend is None:
        backend = MemoryCacheBackend()
    cache_manager = CacheManager(backend)
    return cache_manager


def cache_result(cache_backend, ttl: int = 300, key_prefix: str = ""):
    """Decorator to cache function results."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_parts = [key_prefix, func.__name__] if key_prefix else [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_result = asyncio.run(cache_backend.get(cache_key))
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            asyncio.run(cache_backend.set(cache_key, result, ttl))
            return result

        return wrapper

    return decorator


def async_cache_result(cache_backend, ttl: int = 300, key_prefix: str = ""):
    """Decorator to cache async function results."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_parts = [key_prefix, func.__name__] if key_prefix else [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_result = await cache_backend.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_backend.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator
