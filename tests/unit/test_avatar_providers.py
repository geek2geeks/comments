"""
Unit tests for Avatar Providers

Tests each avatar provider with mocked external dependencies.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from providers.avatar_provider import (
    LiveAvatarProvider, ScraperAvatarProvider, 
    GeneratorAvatarProvider, InitialsAvatarProvider
)


class TestLiveAvatarProvider:
    """Test LiveAvatarProvider"""
    
    @pytest.fixture
    def provider(self):
        return LiveAvatarProvider()
    
    def test_properties(self, provider):
        """Test provider properties"""
        assert provider.priority == 10
        assert provider.source_name == "live"
    
    @pytest.mark.asyncio
    async def test_get_avatar_no_url(self, provider):
        """Test that None is returned when no live_avatar_url provided"""
        result = await provider.get_avatar("testuser")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_avatar_success(self, provider):
        """Test successful avatar capture"""
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"fake_image_data")
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await provider.get_avatar("testuser", "Test User", "http://example.com/avatar.jpg")
            
            assert result is not None
            assert result.username == "testuser"
            assert result.nickname == "Test User"
            assert result.source == "live"
            assert result.priority == 10


class TestInitialsAvatarProvider:
    """Test InitialsAvatarProvider (should always work)"""
    
    @pytest.fixture
    def provider(self):
        return InitialsAvatarProvider()
    
    def test_properties(self, provider):
        """Test provider properties"""
        assert provider.priority == 1
        assert provider.source_name == "initials"
    
    @pytest.mark.asyncio
    async def test_get_avatar_always_works(self, provider):
        """Test that initials provider always returns a result"""
        result = await provider.get_avatar("testuser", "Test User")
        
        assert result is not None
        assert result.username == "testuser"
        assert result.nickname == "Test User"
        assert result.source == "initials"
        assert result.priority == 1
        assert result.avatar_data_url.startswith("data:image/svg+xml;base64,")
    
    def test_get_initials(self, provider):
        """Test initials extraction logic"""
        # Test with display name and username
        initials = provider._get_initials("John Doe", "johndoe")
        assert initials == "JD"
        
        # Test with single name
        initials = provider._get_initials("John", "johndoe") 
        assert initials == "JO"
        
        # Test with short username fallback
        initials = provider._get_initials("", "ab")
        assert initials == "AB"


if __name__ == "__main__":
    # Simple test runner for verification
    async def run_tests():
        provider = InitialsAvatarProvider()
        result = await provider.get_avatar("testuser", "Test User")
        print(f"✅ Initials provider test passed: {result is not None}")
        
        live_provider = LiveAvatarProvider()
        result = await live_provider.get_avatar("testuser")  # No URL provided
        print(f"✅ Live provider test passed: {result is None}")
        
    asyncio.run(run_tests())
    print("✅ All provider tests completed!")