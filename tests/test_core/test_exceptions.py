import pytest
from fastapi import HTTPException
from core.exceptions import (
    TikTokConnectionError,
    ProfileNotFoundError,
    ValidationError,
    RateLimitError,
    AuthenticationError,
    CacheError,
    WebSocketError,
    convert_to_http_exception
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_tiktok_connection_error(self):
        """Test TikTokConnectionError creation and properties."""
        error = TikTokConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert error.status_code == 503
        assert error.error_code == "TIKTOK_CONNECTION_ERROR"

    def test_profile_not_found_error(self):
        """Test ProfileNotFoundError creation and properties."""
        error = ProfileNotFoundError("Profile not found")
        assert str(error) == "Profile not found"
        assert error.status_code == 404
        assert error.error_code == "PROFILE_NOT_FOUND"

    def test_validation_error(self):
        """Test ValidationError creation and properties."""
        error = ValidationError("Invalid input")
        assert str(error) == "Invalid input"
        assert error.status_code == 400
        assert error.error_code == "VALIDATION_ERROR"

    def test_rate_limit_error(self):
        """Test RateLimitError creation and properties."""
        error = RateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert error.status_code == 429
        assert error.error_code == "RATE_LIMIT_EXCEEDED"

    def test_authentication_error(self):
        """Test AuthenticationError creation and properties."""
        error = AuthenticationError("Invalid API key")
        assert str(error) == "Invalid API key"
        assert error.status_code == 401
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_cache_error(self):
        """Test CacheError creation and properties."""
        error = CacheError("Cache operation failed")
        assert str(error) == "Cache operation failed"
        assert error.status_code == 500
        assert error.error_code == "CACHE_ERROR"

    def test_websocket_error(self):
        """Test WebSocketError creation and properties."""
        error = WebSocketError("WebSocket connection failed")
        assert str(error) == "WebSocket connection failed"
        assert error.status_code == 500
        assert error.error_code == "WEBSOCKET_ERROR"


class TestConvertToHttpException:
    """Test convert_to_http_exception function."""

    def test_convert_tiktok_connection_error(self):
        """Test converting TikTokConnectionError to HTTPException."""
        error = TikTokConnectionError("Connection failed")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 503
        assert http_error.detail == {
            "error": "TIKTOK_CONNECTION_ERROR",
            "message": "Connection failed",
            "status_code": 503
        }

    def test_convert_profile_not_found_error(self):
        """Test converting ProfileNotFoundError to HTTPException."""
        error = ProfileNotFoundError("Profile not found")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 404
        assert http_error.detail == {
            "error": "PROFILE_NOT_FOUND",
            "message": "Profile not found",
            "status_code": 404
        }

    def test_convert_validation_error(self):
        """Test converting ValidationError to HTTPException."""
        error = ValidationError("Invalid input")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 400
        assert http_error.detail == {
            "error": "VALIDATION_ERROR",
            "message": "Invalid input",
            "status_code": 400
        }

    def test_convert_rate_limit_error(self):
        """Test converting RateLimitError to HTTPException."""
        error = RateLimitError("Rate limit exceeded")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 429
        assert http_error.detail == {
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Rate limit exceeded",
            "status_code": 429
        }

    def test_convert_authentication_error(self):
        """Test converting AuthenticationError to HTTPException."""
        error = AuthenticationError("Invalid API key")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 401
        assert http_error.detail == {
            "error": "AUTHENTICATION_ERROR",
            "message": "Invalid API key",
            "status_code": 401
        }

    def test_convert_cache_error(self):
        """Test converting CacheError to HTTPException."""
        error = CacheError("Cache operation failed")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 500
        assert http_error.detail == {
            "error": "CACHE_ERROR",
            "message": "Cache operation failed",
            "status_code": 500
        }

    def test_convert_websocket_error(self):
        """Test converting WebSocketError to HTTPException."""
        error = WebSocketError("WebSocket connection failed")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 500
        assert http_error.detail == {
            "error": "WEBSOCKET_ERROR",
            "message": "WebSocket connection failed",
            "status_code": 500
        }

    def test_convert_generic_exception(self):
        """Test converting generic Exception to HTTPException."""
        error = Exception("Generic error")
        http_error = convert_to_http_exception(error)
        
        assert isinstance(http_error, HTTPException)
        assert http_error.status_code == 500
        assert http_error.detail == {
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Generic error",
            "status_code": 500
        }