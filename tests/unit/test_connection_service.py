"""
Unit tests for ConnectionService

Tests the connection management service with mocked providers.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from services.connection_service import ConnectionService
from core.models import Comment


class TestConnectionService:
    """Test ConnectionService"""
    
    @pytest.fixture
    def service(self):
        """Create ConnectionService instance"""
        return ConnectionService()
    
    def test_initial_state(self, service):
        """Test service initial state"""
        assert len(service.active_listeners) == 0
        assert len(service.session_callbacks) == 0
        assert not service.is_connected("test_session")
    
    @pytest.mark.asyncio
    async def test_start_stream_success(self, service):
        """Test successful stream start"""
        # Mock TikTokLiveProvider
        mock_provider = Mock()
        mock_provider.start_listening = AsyncMock(return_value=True)
        mock_provider.is_connected = Mock(return_value=True)
        
        with patch('services.connection_service.TikTokLiveProvider', return_value=mock_provider):
            callback = Mock()
            result = await service.start_stream("test_session", "testuser", callback)
            
            assert result is True
            assert "test_session" in service.active_listeners
            assert "test_session" in service.session_callbacks
            assert service.is_connected("test_session")
    
    @pytest.mark.asyncio
    async def test_start_stream_failure(self, service):
        """Test stream start failure"""
        # Mock TikTokLiveProvider that fails to start
        mock_provider = Mock()
        mock_provider.start_listening = AsyncMock(return_value=False)
        
        with patch('services.connection_service.TikTokLiveProvider', return_value=mock_provider):
            callback = Mock()
            result = await service.start_stream("test_session", "testuser", callback)
            
            assert result is False
            assert "test_session" not in service.active_listeners
            assert "test_session" not in service.session_callbacks
    
    @pytest.mark.asyncio
    async def test_stop_stream(self, service):
        """Test stopping a stream"""
        # Set up mock active listener
        mock_listener = Mock()
        mock_listener.stop_listening = AsyncMock()
        
        service.active_listeners["test_session"] = mock_listener
        service.session_callbacks["test_session"] = Mock()
        
        result = await service.stop_stream("test_session")
        
        assert result is True
        assert "test_session" not in service.active_listeners
        assert "test_session" not in service.session_callbacks
        mock_listener.stop_listening.assert_called_once()
    
    def test_get_connection_stats(self, service):
        """Test connection statistics"""
        # Add mock listeners
        mock_connected = Mock()
        mock_connected.is_connected = Mock(return_value=True)
        
        mock_disconnected = Mock()
        mock_disconnected.is_connected = Mock(return_value=False)
        
        service.active_listeners["session1"] = mock_connected
        service.active_listeners["session2"] = mock_disconnected
        
        stats = service.get_connection_stats()
        
        assert stats["total_sessions"] == 2
        assert stats["connected_sessions"] == 1
        assert stats["disconnected_sessions"] == 1
        assert "session1" in stats["active_session_ids"]
        assert "session2" in stats["active_session_ids"]


if __name__ == "__main__":
    # Simple test runner
    async def run_tests():
        service = ConnectionService()
        
        # Test initial state
        assert len(service.active_listeners) == 0
        print("✅ Initial state test passed")
        
        # Test stats with no connections
        stats = service.get_connection_stats()
        assert stats["total_sessions"] == 0
        print("✅ Stats test passed")
        
        # Test stop on non-existent session
        result = await service.stop_stream("nonexistent")
        assert result is False
        print("✅ Stop non-existent test passed")
        
    asyncio.run(run_tests())
    print("✅ All connection service tests completed!")