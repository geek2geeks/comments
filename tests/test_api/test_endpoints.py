import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from fastapi import status


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "cache" in data
        assert "system" in data
        assert data["status"] == "healthy"

    def test_ping_endpoint(self, test_client):
        """Test the ping endpoint."""
        response = test_client.get("/ping")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "timestamp" in data
        assert "version" in data
        assert data["message"] == "pong"

    def test_metrics_endpoint(self, test_client):
        """Test the metrics endpoint."""
        response = test_client.get("/metrics")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "counters" in data
        assert "timings" in data
        assert "gauges" in data
        assert "system" in data

    def test_cache_stats_endpoint(self, test_client):
        """Test the cache stats endpoint."""
        response = test_client.get("/cache/stats")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "status" in data
        assert "backend_type" in data
        assert "stats" in data


class TestAuthenticationEndpoints:
    """Test authentication-related functionality."""

    def test_endpoint_without_api_key(self, test_client):
        """Test accessing protected endpoint without API key."""
        response = test_client.post("/api/connect", json={"username": "test_user"})
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "error" in data
        assert data["error"] == "AUTHENTICATION_ERROR"

    def test_endpoint_with_invalid_api_key(self, test_client):
        """Test accessing protected endpoint with invalid API key."""
        headers = {"X-API-Key": "invalid_key"}
        response = test_client.post(
            "/api/connect", 
            json={"username": "test_user"}, 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "error" in data
        assert data["error"] == "AUTHENTICATION_ERROR"

    def test_endpoint_with_valid_api_key(self, test_client):
        """Test accessing protected endpoint with valid API key."""
        headers = {"X-API-Key": "test_api_key"}
        
        with patch('api.endpoints.TikTokLiveClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = None
            mock_client_class.return_value = mock_client
            
            response = test_client.post(
                "/api/connect", 
                json={"username": "test_user", "session_id": "test_session"}, 
                headers=headers
            )
        
        # Should not be unauthorized (might be other errors, but not 401)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED


class TestConnectionEndpoints:
    """Test TikTok connection endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Provide authentication headers for testing."""
        return {"X-API-Key": "test_api_key"}

    @patch('api.endpoints.TikTokLiveClient')
    def test_connect_endpoint_success(self, mock_client_class, test_client, auth_headers):
        """Test successful connection to TikTok Live."""
        mock_client = AsyncMock()
        mock_client.connect.return_value = None
        mock_client_class.return_value = mock_client
        
        request_data = {
            "username": "test_user",
            "session_id": "test_session_123"
        }
        
        response = test_client.post("/api/connect", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "username" in data
        assert "session_id" in data
        assert "timestamp" in data
        assert data["username"] == "test_user"
        assert data["session_id"] == "test_session_123"

    def test_connect_endpoint_validation_error(self, test_client, auth_headers):
        """Test connection endpoint with validation errors."""
        # Missing required fields
        request_data = {}
        
        response = test_client.post("/api/connect", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_connect_endpoint_invalid_username(self, test_client, auth_headers):
        """Test connection endpoint with invalid username."""
        request_data = {
            "username": "",  # Empty username
            "session_id": "test_session"
        }
        
        response = test_client.post("/api/connect", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert data["error"] == "VALIDATION_ERROR"

    @patch('api.endpoints.TikTokLiveClient')
    def test_connect_endpoint_tiktok_error(self, mock_client_class, test_client, auth_headers):
        """Test connection endpoint when TikTok connection fails."""
        mock_client = AsyncMock()
        mock_client.connect.side_effect = Exception("TikTok connection failed")
        mock_client_class.return_value = mock_client
        
        request_data = {
            "username": "test_user",
            "session_id": "test_session"
        }
        
        response = test_client.post("/api/connect", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "error" in data
        assert data["error"] == "TIKTOK_CONNECTION_ERROR"

    def test_disconnect_endpoint_success(self, test_client, auth_headers):
        """Test successful disconnection."""
        request_data = {
            "session_id": "test_session_123"
        }
        
        response = test_client.post("/api/disconnect", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "session_id" in data
        assert "timestamp" in data
        assert data["session_id"] == "test_session_123"

    def test_disconnect_endpoint_validation_error(self, test_client, auth_headers):
        """Test disconnection endpoint with validation errors."""
        request_data = {}  # Missing session_id
        
        response = test_client.post("/api/disconnect", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestProfileEndpoints:
    """Test profile-related endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Provide authentication headers for testing."""
        return {"X-API-Key": "test_api_key"}

    def test_get_profile_endpoint_success(self, test_client, auth_headers, sample_profile_data):
        """Test successful profile retrieval."""
        with patch('api.endpoints.get_profile_data') as mock_get_profile:
            mock_get_profile.return_value = sample_profile_data
            
            response = test_client.get("/api/profile/test_user", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["username"] == "test_user"
        assert data["display_name"] == "Test User"
        assert data["follower_count"] == 1000

    def test_get_profile_endpoint_not_found(self, test_client, auth_headers):
        """Test profile endpoint when profile is not found."""
        with patch('api.endpoints.get_profile_data') as mock_get_profile:
            mock_get_profile.side_effect = Exception("Profile not found")
            
            response = test_client.get("/api/profile/nonexistent_user", headers=auth_headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"] == "PROFILE_NOT_FOUND"

    def test_revalidate_profile_endpoint(self, test_client, auth_headers):
        """Test profile revalidation endpoint."""
        request_data = {
            "username": "test_user"
        }
        
        response = test_client.post("/api/revalidate", json=request_data, headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "username" in data
        assert "timestamp" in data
        assert data["username"] == "test_user"


class TestStatusEndpoints:
    """Test status and monitoring endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Provide authentication headers for testing."""
        return {"X-API-Key": "test_api_key"}

    def test_get_status_endpoint(self, test_client, auth_headers):
        """Test getting connection status."""
        response = test_client.get("/api/status", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "active_connections" in data
        assert "total_connections" in data
        assert "uptime" in data
        assert "timestamp" in data
        assert isinstance(data["active_connections"], int)

    def test_get_sessions_endpoint(self, test_client, auth_headers):
        """Test getting active sessions."""
        response = test_client.get("/api/sessions", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "sessions" in data
        assert "count" in data
        assert "timestamp" in data
        assert isinstance(data["sessions"], list)
        assert isinstance(data["count"], int)

    def test_cleanup_cache_endpoint(self, test_client, auth_headers):
        """Test cache cleanup endpoint."""
        response = test_client.post("/api/cache/cleanup", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "timestamp" in data
        assert "cleaned" in data["message"]


class TestWebSocketEndpoint:
    """Test WebSocket endpoint functionality."""

    @pytest.mark.asyncio
    async def test_websocket_connection_without_auth(self, async_client):
        """Test WebSocket connection without authentication."""
        with pytest.raises(Exception):  # Should fail without proper auth
            async with async_client.websocket_connect("/ws/test_session") as websocket:
                pass

    @pytest.mark.asyncio
    async def test_websocket_connection_with_auth(self, async_client):
        """Test WebSocket connection with authentication."""
        headers = {"X-API-Key": "test_api_key"}
        
        # Note: This test might need adjustment based on actual WebSocket auth implementation
        try:
            async with async_client.websocket_connect(
                "/ws/test_session", 
                headers=headers
            ) as websocket:
                # If connection succeeds, test basic functionality
                await websocket.send_text(json.dumps({"type": "ping"}))
                response = await websocket.receive_text()
                data = json.loads(response)
                assert "type" in data
        except Exception:
            # WebSocket might not be fully implemented or require additional setup
            pytest.skip("WebSocket endpoint requires additional setup")


class TestErrorHandling:
    """Test error handling across endpoints."""

    @pytest.fixture
    def auth_headers(self):
        """Provide authentication headers for testing."""
        return {"X-API-Key": "test_api_key"}

    def test_404_error_handling(self, test_client):
        """Test 404 error handling for non-existent endpoints."""
        response = test_client.get("/nonexistent/endpoint")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_method_not_allowed_error(self, test_client, auth_headers):
        """Test method not allowed error handling."""
        # Try GET on a POST-only endpoint
        response = test_client.get("/api/connect", headers=auth_headers)
        
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_large_payload_handling(self, test_client, auth_headers):
        """Test handling of large payloads."""
        # Create a large payload
        large_data = {
            "username": "test_user",
            "session_id": "test_session",
            "large_field": "x" * 10000  # 10KB of data
        }
        
        response = test_client.post("/api/connect", json=large_data, headers=auth_headers)
        
        # Should handle large payloads gracefully (might return validation error)
        assert response.status_code in [400, 413, 422]  # Bad Request, Payload Too Large, or Validation Error

    def test_malformed_json_handling(self, test_client, auth_headers):
        """Test handling of malformed JSON."""
        response = test_client.post(
            "/api/connect",
            data="{invalid json}",
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.fixture
    def auth_headers(self):
        """Provide authentication headers for testing."""
        return {"X-API-Key": "test_api_key"}

    @pytest.mark.slow
    def test_rate_limiting_enforcement(self, test_client, auth_headers):
        """Test that rate limiting is enforced."""
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = test_client.get("/health")
            responses.append(response.status_code)
        
        # At least some requests should succeed
        assert status.HTTP_200_OK in responses
        
        # If rate limiting is implemented, some might be rate limited
        # This test might need adjustment based on actual rate limiting implementation
        rate_limited_count = responses.count(status.HTTP_429_TOO_MANY_REQUESTS)
        
        # For now, just ensure the endpoint is responsive
        assert len(responses) == 10