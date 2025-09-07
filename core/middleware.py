"""
Application Middleware for the Profile API.

This module defines a collection of FastAPI middleware responsible for handling
cross-cutting concerns such as request correlation, error handling, performance
monitoring, and security. These middleware components process every request and
response, ensuring consistency and robustness across the application.

Key Middleware Components:
- `CorrelationMiddleware`: Assigns a unique correlation ID to every incoming
  request, which is then used in logs to trace the request's entire lifecycle.
- `ErrorHandlingMiddleware`: A centralized error handler that catches all
  exceptions (both custom `ProfileAPIException` types and standard HTTP
  exceptions) and transforms them into standardized JSON error responses.
- `PerformanceMiddleware`: Logs the start and end of each request, calculates
  the processing time, and adds a `X-Process-Time` header to the response.
  It also logs slow requests that exceed a predefined threshold.
- `SecurityMiddleware`: Implements basic security measures, including IP-based
  rate limiting and the addition of standard security headers (e.g.,
  `X-Content-Type-Options`, `X-Frame-Options`) to every response.
- `RequestValidationMiddleware`: Performs initial validation on incoming requests,
  such as checking the request size and content type, to reject invalid
  requests early in the processing pipeline.

Architectural Design:
- Layered Processing Pipeline: The middleware components are arranged in a
  specific order to form a request processing pipeline. For example, the
  `CorrelationMiddleware` runs first to ensure the correlation ID is available
  to all subsequent middleware and application code.
- Separation of Concerns: Each middleware class has a single, well-defined
  responsibility. This makes them easy to understand, test, and maintain.
- Starlette's `BaseHTTPMiddleware`: The middleware are built on Starlette's
  `BaseHTTPMiddleware`, which provides a standard and efficient way to implement
  custom middleware for ASGI applications like FastAPI.
- Configuration and Extensibility: While this implementation contains some hard-
  coded values (e.g., rate limits), it is designed to be easily extensible.
  In a production system, these values would be externalized to a configuration
  file or environment variables.
"""

import time
import uuid
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logging_config import set_correlation_id, get_logger
from .exceptions import ProfileAPIException, to_http_exception

logger = get_logger("core.middleware")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs to requests"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract correlation ID
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )

        # Set correlation ID in context
        set_correlation_id(correlation_id)

        # Add to request state for access in endpoints
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response

        except ProfileAPIException as e:
            # Handle custom application exceptions
            logger.error(
                f"Application error: {str(e)}",
                extra={
                    "error_type": type(e).__name__,
                    "error_code": e.error_code,
                    "path": request.url.path,
                    "method": request.method,
                },
            )

            http_exc = to_http_exception(e)
            return JSONResponse(
                status_code=http_exc.status_code,
                content={
                    "error": {
                        "type": type(e).__name__,
                        "code": e.error_code,
                        "message": str(e),
                        "correlation_id": getattr(
                            request.state, "correlation_id", None
                        ),
                    }
                },
            )

        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            logger.warning(
                f"HTTP exception: {e.status_code} - {e.detail}",
                extra={
                    "status_code": e.status_code,
                    "path": request.url.path,
                    "method": request.method,
                },
            )

            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "type": "HTTPException",
                        "code": f"HTTP_{e.status_code}",
                        "message": e.detail,
                        "correlation_id": getattr(
                            request.state, "correlation_id", None
                        ),
                    }
                },
            )

        except Exception as e:
            # Handle unexpected exceptions
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={
                    "error_type": type(e).__name__,
                    "path": request.url.path,
                    "method": request.method,
                },
                exc_info=True,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "type": "InternalServerError",
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred",
                        "correlation_id": getattr(
                            request.state, "correlation_id", None
                        ),
                    }
                },
            )


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring and logging"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None,
            },
        )

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add performance headers
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))

        # Log request completion
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time_ms": round(process_time * 1000, 2),
                "response_size": len(response.body)
                if hasattr(response, "body")
                else None,
            },
        )

        # Log slow requests
        if process_time > 1.0:  # Log requests taking more than 1 second
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": round(process_time * 1000, 2),
                    "threshold_exceeded": True,
                },
            )

        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for security enhancements"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.blocked_ips = set()  # In production, use Redis or database
        self.request_counts = {}  # In production, use Redis for distributed rate limiting

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            logger.warning(
                f"Blocked IP attempted access: {client_ip}",
                extra={"client_ip": client_ip, "path": request.url.path},
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "type": "Forbidden",
                        "code": "IP_BLOCKED",
                        "message": "Access denied",
                    }
                },
            )

        # Basic rate limiting (simplified - use Redis in production)
        current_time = int(time.time())
        minute_key = f"{client_ip}:{current_time // 60}"

        if minute_key not in self.request_counts:
            self.request_counts[minute_key] = 0

        self.request_counts[minute_key] += 1

        # Allow 100 requests per minute per IP
        if self.request_counts[minute_key] > 100:
            logger.warning(
                f"Rate limit exceeded for IP: {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "requests_count": self.request_counts[minute_key],
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "type": "RateLimitExceeded",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests",
                        "retry_after": 60,
                    }
                },
                headers={"Retry-After": "60"},
            )

        # Clean up old entries (keep only last 2 minutes)
        keys_to_remove = [
            key
            for key in self.request_counts.keys()
            if int(key.split(":")[1]) < (current_time // 60) - 1
        ]
        for key in keys_to_remove:
            del self.request_counts[key]

        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and sanitization"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.max_request_size = 10 * 1024 * 1024  # 10MB

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            logger.warning(
                f"Request too large: {content_length} bytes",
                extra={
                    "content_length": int(content_length),
                    "max_size": self.max_request_size,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "type": "PayloadTooLarge",
                        "code": "REQUEST_TOO_LARGE",
                        "message": f"Request size exceeds maximum allowed size of {self.max_request_size} bytes",
                    }
                },
            )

        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            allowed_types = [
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ]

            if not any(allowed_type in content_type for allowed_type in allowed_types):
                logger.warning(
                    f"Invalid content type: {content_type}",
                    extra={
                        "content_type": content_type,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": {
                            "type": "UnsupportedMediaType",
                            "code": "INVALID_CONTENT_TYPE",
                            "message": f"Content type '{content_type}' is not supported",
                        }
                    },
                )

        # Process request
        response = await call_next(request)

        return response


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxy headers"""
    # Check for forwarded headers (when behind a proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


def create_error_response(
    error_type: str,
    error_code: str,
    message: str,
    status_code: int = 400,
    correlation_id: str = None,
    details: Dict[str, Any] = None,
) -> JSONResponse:
    """Create standardized error response"""

    error_data = {"error": {"type": error_type, "code": error_code, "message": message}}

    if correlation_id:
        error_data["error"]["correlation_id"] = correlation_id

    if details:
        error_data["error"]["details"] = details

    return JSONResponse(status_code=status_code, content=error_data)
