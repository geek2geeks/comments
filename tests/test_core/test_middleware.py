import pytest
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.middleware import (
    CorrelationMiddleware,
    ErrorHandlingMiddleware,
    PerformanceMiddleware,
    SecurityMiddleware,
    RequestValidationMiddleware,
    get_client_ip,
    create_error_response
)
from core.exceptions import ValidationError, RateLimitError


class TestCorrelationMiddleware:
    """Test CorrelationMiddleware functionality."""

    @pytest.fixture
    def app_with_correlation_middleware(self):
        """Create a FastAPI app with CorrelationMiddleware for testing."""
        app = FastAPI()
        app.add_middleware(CorrelationMiddleware)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"correlation_id": request.state.correlation_id}
        
        return app

    def test_correlation_id_generation(self, app_with_correlation_middleware):
        """Test that correlation ID is generated for requests."""
        client = TestClient(app_with_correlation_middleware)
        response = client.get("/test")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "correlation_id" in data
        assert len(data["correlation_id"]) > 0
        assert "X-Correlation-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == data["correlation_id"]

    def test_existing_correlation_id_preserved(self, app_with_correlation_middleware):
        """Test that existing correlation ID is preserved."""
        client = TestClient(app_with_correlation_middleware)
        existing_id = "existing-correlation-id-123"
        
        response = client.get("/test", headers={"X-Correlation-ID": existing_id})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["correlation_id"] == existing_id
        assert response.headers["X-Correlation-ID"] == existing_id

    def test_multiple_requests_different_ids(self, app_with_correlation_middleware):
        """Test that different requests get different correlation IDs."""
        client = TestClient(app_with_correlation_middleware)
        
        response1 = client.get("/test")
        response2 = client.get("/test")
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["correlation_id"] != data2["correlation_id"]


class TestErrorHandlingMiddleware:
    """Test ErrorHandlingMiddleware functionality."""

    @pytest.fixture
    def app_with_error_middleware(self):
        """Create a FastAPI app with ErrorHandlingMiddleware for testing."""
        app = FastAPI()
        app.add_middleware(ErrorHandlingMiddleware)
        
        @app.get("/test/validation-error")
        async def validation_error_endpoint():
            raise ValidationError("Invalid input data")
        
        @app.get("/test/rate-limit-error")
        async def rate_limit_error_endpoint():
            raise RateLimitError("Rate limit exceeded")
        
        @app.get("/test/generic-error")
        async def generic_error_endpoint():
            raise Exception("Something went wrong")
        
        @app.get("/test/success")
        async def success_endpoint():
            return {"message": "success"}
        
        return app

    def test_validation_error_handling(self, app_with_error_middleware):
        """Test handling of ValidationError."""
        client = TestClient(app_with_error_middleware)
        response = client.get("/test/validation-error")
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["error"] == "VALIDATION_ERROR"
        assert data["message"] == "Invalid input data"
        assert data["status_code"] == 400
        assert "timestamp" in data

    def test_rate_limit_error_handling(self, app_with_error_middleware):
        """Test handling of RateLimitError."""
        client = TestClient(app_with_error_middleware)
        response = client.get("/test/rate-limit-error")
        
        assert response.status_code == 429
        data = response.json()
        
        assert data["error"] == "RATE_LIMIT_EXCEEDED"
        assert data["message"] == "Rate limit exceeded"
        assert data["status_code"] == 429

    def test_generic_error_handling(self, app_with_error_middleware):
        """Test handling of generic exceptions."""
        client = TestClient(app_with_error_middleware)
        response = client.get("/test/generic-error")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["error"] == "INTERNAL_SERVER_ERROR"
        assert data["message"] == "Something went wrong"
        assert data["status_code"] == 500

    def test_successful_request_passthrough(self, app_with_error_middleware):
        """Test that successful requests pass through unchanged."""
        client = TestClient(app_with_error_middleware)
        response = client.get("/test/success")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "success"


class TestPerformanceMiddleware:
    """Test PerformanceMiddleware functionality."""

    @pytest.fixture
    def mock_metrics_collector(self):
        """Create a mock metrics collector."""
        collector = Mock()
        collector.increment_counter = Mock()
        collector.record_timing = Mock()
        return collector

    @pytest.fixture
    def app_with_performance_middleware(self, mock_metrics_collector):
        """Create a FastAPI app with PerformanceMiddleware for testing."""
        app = FastAPI()
        
        # Inject the mock metrics collector
        app.state.metrics_collector = mock_metrics_collector
        app.add_middleware(PerformanceMiddleware)
        
        @app.get("/test/fast")
        async def fast_endpoint():
            return {"message": "fast"}
        
        @app.get("/test/slow")
        async def slow_endpoint():
            import asyncio
            await asyncio.sleep(0.1)
            return {"message": "slow"}
        
        return app

    def test_request_timing_recorded(self, app_with_performance_middleware, mock_metrics_collector):
        """Test that request timing is recorded."""
        client = TestClient(app_with_performance_middleware)
        response = client.get("/test/fast")
        
        assert response.status_code == 200
        
        # Verify metrics were recorded
        mock_metrics_collector.increment_counter.assert_called()
        mock_metrics_collector.record_timing.assert_called()
        
        # Check that timing was recorded for the correct endpoint
        timing_calls = mock_metrics_collector.record_timing.call_args_list
        assert len(timing_calls) > 0
        
        # Verify the timing call includes the endpoint path
        timing_call = timing_calls[0]
        assert "GET /test/fast" in str(timing_call)

    def test_response_headers_added(self, app_with_performance_middleware):
        """Test that performance headers are added to response."""
        client = TestClient(app_with_performance_middleware)
        response = client.get("/test/fast")
        
        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        
        # Response time should be a valid float
        response_time = float(response.headers["X-Response-Time"])
        assert response_time >= 0

    def test_slow_request_timing(self, app_with_performance_middleware, mock_metrics_collector):
        """Test timing measurement for slower requests."""
        client = TestClient(app_with_performance_middleware)
        response = client.get("/test/slow")
        
        assert response.status_code == 200
        
        # Response time should reflect the sleep
        response_time = float(response.headers["X-Response-Time"])
        assert response_time >= 0.1  # Should be at least 100ms


class TestSecurityMiddleware:
    """Test SecurityMiddleware functionality."""

    @pytest.fixture
    def app_with_security_middleware(self):
        """Create a FastAPI app with SecurityMiddleware for testing."""
        app = FastAPI()
        app.add_middleware(SecurityMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "secure"}
        
        return app

    def test_security_headers_added(self, app_with_security_middleware):
        """Test that security headers are added to responses."""
        client = TestClient(app_with_security_middleware)
        response = client.get("/test")
        
        assert response.status_code == 200
        
        # Check for security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_server_header_removed(self, app_with_security_middleware):
        """Test that server header is removed or modified."""
        client = TestClient(app_with_security_middleware)
        response = client.get("/test")
        
        # Server header should either be removed or not reveal FastAPI/Uvicorn
        server_header = response.headers.get("server", "")
        assert "fastapi" not in server_header.lower()
        assert "uvicorn" not in server_header.lower()


class TestRequestValidationMiddleware:
    """Test RequestValidationMiddleware functionality."""

    @pytest.fixture
    def app_with_validation_middleware(self):
        """Create a FastAPI app with RequestValidationMiddleware for testing."""
        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)
        
        @app.post("/test")
        async def test_endpoint(request: Request):
            body = await request.body()
            return {"received": len(body)}
        
        return app

    def test_valid_content_type(self, app_with_validation_middleware):
        """Test that valid content types are accepted."""
        client = TestClient(app_with_validation_middleware)
        response = client.post(
            "/test",
            json={"test": "data"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200

    def test_invalid_content_type(self, app_with_validation_middleware):
        """Test that invalid content types are rejected."""
        client = TestClient(app_with_validation_middleware)
        response = client.post(
            "/test",
            data="test data",
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "content type" in data["message"].lower()

    def test_oversized_request_body(self, app_with_validation_middleware):
        """Test that oversized request bodies are rejected."""
        client = TestClient(app_with_validation_middleware)
        
        # Create a large payload (over 1MB)
        large_data = {"data": "x" * (1024 * 1024 + 1)}
        
        response = client.post(
            "/test",
            json=large_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 413
        data = response.json()
        assert "error" in data
        assert "too large" in data["message"].lower()


class TestUtilityFunctions:
    """Test utility functions used by middleware."""

    def test_get_client_ip_with_forwarded_header(self):
        """Test getting client IP from X-Forwarded-For header."""
        request = Mock()
        request.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}
        request.client = Mock(host="127.0.0.1")
        
        ip = get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_with_real_ip_header(self):
        """Test getting client IP from X-Real-IP header."""
        request = Mock()
        request.headers = {"X-Real-IP": "203.0.113.1"}
        request.client = Mock(host="127.0.0.1")
        
        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_fallback_to_client(self):
        """Test falling back to request.client.host."""
        request = Mock()
        request.headers = {}
        request.client = Mock(host="192.168.1.50")
        
        ip = get_client_ip(request)
        assert ip == "192.168.1.50"

    def test_get_client_ip_no_client(self):
        """Test handling when request.client is None."""
        request = Mock()
        request.headers = {}
        request.client = None
        
        ip = get_client_ip(request)
        assert ip == "unknown"

    def test_create_error_response(self):
        """Test creating standardized error responses."""
        response = create_error_response(
            status_code=400,
            error_code="TEST_ERROR",
            message="Test error message",
            correlation_id="test-correlation-123"
        )
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        # Parse the response content
        content = json.loads(response.body.decode())
        
        assert content["error"] == "TEST_ERROR"
        assert content["message"] == "Test error message"
        assert content["status_code"] == 400
        assert content["correlation_id"] == "test-correlation-123"
        assert "timestamp" in content

    def test_create_error_response_without_correlation_id(self):
        """Test creating error response without correlation ID."""
        response = create_error_response(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Internal server error"
        )
        
        content = json.loads(response.body.decode())
        
        assert content["error"] == "INTERNAL_ERROR"
        assert content["message"] == "Internal server error"
        assert content["status_code"] == 500
        assert content["correlation_id"] is None