"""
Unit tests for Comment Provider

Tests the TikTok Live comment provider with mocked TikTokLive library.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from providers.comment_provider import TikTokLiveProvider
from core.models import Comment


class TestTikTokLiveProvider:
    """Test TikTokLiveProvider"""
    
    @pytest.fixture
    def provider(self):
        return TikTokLiveProvider()
    
    def test_properties(self, provider):
        """Test provider properties"""
        assert provider.source_name == "tiktok"
        assert not provider.is_connected()
    
    @pytest.mark.asyncio
    async def test_start_listening_not_live(self, provider):
        """Test starting listener when user is not live"""
        mock_client = AsyncMock()
        mock_client.is_live = AsyncMock(return_value=False)
        
        with patch('providers.comment_provider.TikTokLiveClient', return_value=mock_client):
            callback = Mock()
            result = await provider.start_listening("testuser", callback)
            
            assert result is False
            assert not provider.is_connected()
    
    @pytest.mark.asyncio  
    async def test_start_listening_success(self, provider):
        """Test successful listener start"""
        mock_client = AsyncMock()
        mock_client.is_live = AsyncMock(return_value=True)
        mock_client.connect = AsyncMock()
        
        with patch('providers.comment_provider.TikTokLiveClient', return_value=mock_client):
            callback = Mock()
            result = await provider.start_listening("testuser", callback)
            
            assert result is True
            assert provider.is_connected()
    
    @pytest.mark.asyncio
    async def test_stop_listening(self, provider):
        """Test stopping the listener"""
        # Set up a mock running state
        provider._running = True
        provider._client = AsyncMock()
        provider._connect_task = AsyncMock()
        provider._connect_task.done.return_value = False
        
        await provider.stop_listening()
        
        assert not provider.is_connected()
        provider._client.disconnect.assert_called_once()
        provider._connect_task.cancel.assert_called_once()


if __name__ == "__main__":
    # Simple test runner for verification
    async def run_tests():
        provider = TikTokLiveProvider()
        
        # Test properties
        assert provider.source_name == "tiktok"
        assert not provider.is_connected()
        print("✅ Provider properties test passed")
        
        # Test stop when not running (should not error)
        await provider.stop_listening()
        print("✅ Stop listening test passed")
        
    asyncio.run(run_tests())
    print("✅ All comment provider tests completed!")