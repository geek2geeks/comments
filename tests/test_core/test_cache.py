import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from core.cache import (
    CacheBackend,
    MemoryCacheBackend,
    RedisCacheBackend,
    CacheManager,
    cache_result,
    async_cache_result
)


class TestMemoryCacheBackend:
    """Test MemoryCacheBackend functionality."""

    @pytest.fixture
    def cache_backend(self):
        """Create a memory cache backend for testing."""
        return MemoryCacheBackend(max_size=100, default_ttl=60)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_backend):
        """Test setting and getting values from cache."""
        await cache_backend.set("test_key", "test_value")
        value = await cache_backend.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache_backend):
        """Test getting a non-existent key returns None."""
        value = await cache_backend.get("nonexistent_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self, cache_backend):
        """Test deleting a key from cache."""
        await cache_backend.set("test_key", "test_value")
        await cache_backend.delete("test_key")
        value = await cache_backend.get("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_exists(self, cache_backend):
        """Test checking if a key exists in cache."""
        await cache_backend.set("test_key", "test_value")
        assert await cache_backend.exists("test_key") is True
        assert await cache_backend.exists("nonexistent_key") is False

    @pytest.mark.asyncio
    async def test_clear(self, cache_backend):
        """Test clearing all cache entries."""
        await cache_backend.set("key1", "value1")
        await cache_backend.set("key2", "value2")
        await cache_backend.clear()
        assert await cache_backend.get("key1") is None
        assert await cache_backend.get("key2") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache_backend):
        """Test that entries expire after TTL."""
        await cache_backend.set("test_key", "test_value", ttl=0.1)  # 0.1 seconds
        assert await cache_backend.get("test_key") == "test_value"
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        assert await cache_backend.get("test_key") is None

    @pytest.mark.asyncio
    async def test_max_size_limit(self):
        """Test that cache respects max_size limit."""
        cache_backend = MemoryCacheBackend(max_size=2)
        
        await cache_backend.set("key1", "value1")
        await cache_backend.set("key2", "value2")
        await cache_backend.set("key3", "value3")  # Should evict oldest
        
        # key1 should be evicted (LRU)
        assert await cache_backend.get("key1") is None
        assert await cache_backend.get("key2") == "value2"
        assert await cache_backend.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_get_stats(self, cache_backend):
        """Test getting cache statistics."""
        await cache_backend.set("key1", "value1")
        await cache_backend.get("key1")  # Hit
        await cache_backend.get("nonexistent")  # Miss
        
        stats = await cache_backend.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1
        assert stats["max_size"] == 100


@pytest.mark.skip(reason="Redis backend is abstract and not implemented yet")
class TestRedisCacheBackend:
    """Test RedisCacheBackend functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock()
        redis_mock.set = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.exists = AsyncMock()
        redis_mock.flushdb = AsyncMock()
        redis_mock.info = AsyncMock(return_value={"used_memory": 1024})
        return redis_mock

    @pytest.fixture
    def cache_backend(self, mock_redis):
        """Create a Redis cache backend for testing."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            return RedisCacheBackend("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_backend, mock_redis):
        """Test setting and getting values from Redis cache."""
        mock_redis.get.return_value = b'"test_value"'
        
        await cache_backend.set("test_key", "test_value")
        value = await cache_backend.get("test_key")
        
        mock_redis.set.assert_called_once()
        mock_redis.get.assert_called_once_with("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache_backend, mock_redis):
        """Test getting a non-existent key returns None."""
        mock_redis.get.return_value = None
        
        value = await cache_backend.get("nonexistent_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self, cache_backend, mock_redis):
        """Test deleting a key from Redis cache."""
        await cache_backend.delete("test_key")
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_exists(self, cache_backend, mock_redis):
        """Test checking if a key exists in Redis cache."""
        mock_redis.exists.return_value = 1
        
        result = await cache_backend.exists("test_key")
        mock_redis.exists.assert_called_once_with("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_clear(self, cache_backend, mock_redis):
        """Test clearing Redis cache."""
        await cache_backend.clear()
        mock_redis.flushdb.assert_called_once()


class TestCacheManager:
    """Test CacheManager functionality."""

    @pytest.fixture
    def cache_manager(self):
        """Create a cache manager for testing."""
        backend = MemoryCacheBackend()
        return CacheManager(backend)

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_manager):
        """Test get_or_set with cache hit."""
        # Pre-populate cache
        await cache_manager.set("test_key", "cached_value")
        
        # Mock function should not be called
        mock_func = AsyncMock(return_value="new_value")
        
        result = await cache_manager.get_or_set("test_key", mock_func)
        
        assert result == "cached_value"
        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_manager):
        """Test get_or_set with cache miss."""
        mock_func = AsyncMock(return_value="new_value")
        
        result = await cache_manager.get_or_set("test_key", mock_func)
        
        assert result == "new_value"
        mock_func.assert_called_once()
        
        # Verify value was cached
        cached_value = await cache_manager.get("test_key")
        assert cached_value == "new_value"

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache_manager):
        """Test invalidating keys by pattern."""
        await cache_manager.set("user:1:profile", "profile1")
        await cache_manager.set("user:2:profile", "profile2")
        await cache_manager.set("session:123", "session_data")
        
        await cache_manager.invalidate_pattern("user:*")
        
        assert await cache_manager.get("user:1:profile") is None
        assert await cache_manager.get("user:2:profile") is None
        assert await cache_manager.get("session:123") == "session_data"

    @pytest.mark.asyncio
    async def test_health_check(self, cache_manager):
        """Test cache health check."""
        health = await cache_manager.health_check()
        
        assert "status" in health
        assert "backend_type" in health
        assert "stats" in health
        assert health["status"] == "healthy"


class TestCacheDecorators:
    """Test cache decorators."""

    @pytest.fixture
    def cache_backend(self):
        """Create a cache backend for decorator testing."""
        return MemoryCacheBackend()

    def test_cache_result_decorator(self, cache_backend):
        """Test cache_result decorator for sync functions."""
        call_count = 0
        
        @cache_result(cache_backend, ttl=60)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # First call should execute function
        result1 = expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(1, 2)
        assert result2 == 3
        assert call_count == 1  # Function not called again

    @pytest.mark.asyncio
    async def test_async_cache_result_decorator(self, cache_backend):
        """Test async_cache_result decorator for async functions."""
        call_count = 0
        
        @async_cache_result(cache_backend, ttl=60)
        async def expensive_async_function(x, y):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate async work
            return x + y
        
        # First call should execute function
        result1 = await expensive_async_function(1, 2)
        assert result1 == 3
        assert call_count == 1
        
        # Second call should use cache
        result2 = await expensive_async_function(1, 2)
        assert result2 == 3
        assert call_count == 1  # Function not called again

    def test_cache_result_with_different_args(self, cache_backend):
        """Test that cache_result creates different cache entries for different arguments."""
        call_count = 0
        
        @cache_result(cache_backend, ttl=60)
        def function_with_args(x, y):
            nonlocal call_count
            call_count += 1
            return x * y
        
        result1 = function_with_args(2, 3)
        result2 = function_with_args(4, 5)
        result3 = function_with_args(2, 3)  # Same as first call
        
        assert result1 == 6
        assert result2 == 20
        assert result3 == 6
        assert call_count == 2  # Only two unique calls