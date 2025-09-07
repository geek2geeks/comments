"""
Unit tests for AvatarService

Tests the service layer with mocked providers and database operations.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from services.avatar_service import AvatarService
from core.models import UserProfile


class TestAvatarService:
    """Test AvatarService"""
    
    @pytest.fixture
    def mock_providers(self):
        """Create mock providers for testing"""
        live_provider = Mock()
        live_provider.priority = 10
        live_provider.get_avatar = AsyncMock()
        
        initials_provider = Mock()
        initials_provider.priority = 1
        initials_provider.get_avatar = AsyncMock(return_value=UserProfile(
            username="testuser",
            nickname="Test User", 
            avatar_url="initials://TU",
            avatar_data_url="data:image/svg+xml;base64,test",
            source="initials",
            priority=1
        ))
        
        return [live_provider, initials_provider]
    
    def test_provider_ordering(self, mock_providers):
        """Test that providers are ordered by priority"""
        service = AvatarService(providers=mock_providers)
        
        # Should be ordered by priority (highest first)
        assert service.providers[0].priority == 10  # live
        assert service.providers[1].priority == 1   # initials
    
    @pytest.mark.asyncio
    async def test_get_profile_fallback_chain(self, mock_providers):
        """Test provider fallback chain"""
        service = AvatarService(providers=mock_providers)
        
        # Mock database operations
        with patch.object(service, '_get_cached_profile', return_value=None), \
             patch.object(service, '_cache_profile') as mock_cache:
            
            # Live provider fails, initials provider succeeds
            mock_providers[0].get_avatar.return_value = None
            
            result = await service.get_user_profile("testuser", "Test User")
            
            assert result is not None
            assert result.source == "initials"
            mock_cache.assert_called_once()


class TestAvatarServiceIntegration:
    """Integration tests for AvatarService"""
    
    @pytest.mark.asyncio
    async def test_service_with_real_initials_provider(self):
        """Test service with real InitialsAvatarProvider"""
        from providers.avatar_provider import InitialsAvatarProvider
        
        service = AvatarService(providers=[InitialsAvatarProvider()])
        
        # Mock database operations to avoid real DB calls
        with patch.object(service, '_get_cached_profile', return_value=None), \
             patch.object(service, '_cache_profile'):
            
            result = await service.get_user_profile("testuser", "Test User")
            
            assert result is not None
            assert result.username == "testuser"
            assert result.source == "initials"
            assert result.priority == 1


if __name__ == "__main__":
    # Simple test runner
    async def run_tests():
        # Test with real provider
        from providers.avatar_provider import InitialsAvatarProvider
        
        service = AvatarService(providers=[InitialsAvatarProvider()])
        
        # Mock database to avoid real operations
        service._get_cached_profile = lambda x: None
        service._cache_profile = lambda x: None
        
        result = await service.get_user_profile("testuser", "Test User")
        print(f"✅ Service test passed: {result is not None and result.source == 'initials'}")
        
        stats = service.get_cache_stats()
        print(f"✅ Stats test passed: {'providers_available' in stats}")
        
    asyncio.run(run_tests())
    print("✅ All avatar service tests completed!")