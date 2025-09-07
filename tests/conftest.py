import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import os
import sys
from typing import AsyncGenerator, Generator

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from core.cache import CacheManager, MemoryCacheBackend
from core.performance import MetricsCollector
from api.endpoints import ConnectionManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager for testing."""
    cache_backend = MemoryCacheBackend()
    return CacheManager(cache_backend)


@pytest.fixture
def mock_metrics_collector():
    """Create a mock metrics collector for testing."""
    return MetricsCollector()


@pytest.fixture
def mock_connection_manager():
    """Create a mock connection manager for testing."""
    manager = Mock(spec=ConnectionManager)
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.get_active_connections = Mock(return_value=[])
    manager.cleanup_inactive_connections = AsyncMock()
    return manager


@pytest.fixture
def mock_tiktok_live_client():
    """Create a mock TikTok Live client for testing."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_connected = False
    return client


@pytest.fixture
def sample_profile_data():
    """Sample profile data for testing."""
    return {
        "username": "test_user",
        "display_name": "Test User",
        "follower_count": 1000,
        "following_count": 500,
        "bio": "Test bio",
        "avatar_url": "https://example.com/avatar.jpg",
        "is_verified": False,
        "is_live": True,
    }


@pytest.fixture
def sample_connection_request():
    """Sample connection request data for testing."""
    return {"username": "test_user", "session_id": "test_session_123"}


@pytest.fixture
def sample_websocket_message():
    """Sample WebSocket message for testing."""
    return {
        "type": "comment",
        "data": {
            "user": "test_user",
            "comment": "Hello world!",
            "timestamp": "2024-01-01T00:00:00Z",
        },
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("API_KEY", "test_api_key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.error = Mock()
    logger.warning = Mock()
    logger.debug = Mock()
    return logger


class AsyncContextManager:
    """Helper class for testing async context managers."""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """Create an async context manager for testing."""
    return AsyncContextManager
