"""Security Middleware

Provides comprehensive security middleware including rate limiting,
authentication, input validation, and security headers.
"""

import time
from fastapi import Request
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.logging_config import get_logger, correlation_id
from core.rate_limiter import get_rate_limiter
from core.auth import get_auth_service, User, APIKey
from core.validation import RequestValidator
from core.exceptions import AuthenticationError, ValidationError

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""

    def __init__(self, app, default_rule: str = "api"):
        super().__init__(app)
        self.default_rule = default_rule

    async def dispatch(self, request: Request, call_next):
        rate_limiter = get_rate_limiter()

        # Get client identifier (IP address)
        client_ip = self.get_client_ip(request)

        # Determine rate limit rule based on endpoint
        rule_key = self.get_rate_limit_rule(request)

        try:
            # Check rate limit
            allowed, info = rate_limiter.check_rate_limit(client_ip, rule_key)

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_ip} on {request.url.path}",
                    extra={
                        "client_ip": client_ip,
                        "rule": rule_key,
                        "retry_after": info["retry_after"],
                    },
                )

                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests",
                        "retry_after": info["retry_after"],
                        "remaining": info["remaining"],
                    },
                    headers={
                        "Retry-After": str(int(info["retry_after"])),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(int(info["reset_time"].timestamp())),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers to response
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(
                int(info["reset_time"].timestamp())
            )

            return response

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue without rate limiting on error
            return await call_next(request)

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def get_rate_limit_rule(self, request: Request) -> str:
        """Determine rate limit rule based on request"""
        path = request.url.path

        # Stricter limits for authentication endpoints
        if "/auth/" in path or "/login" in path:
            return "auth"

        # Stricter limits for connection endpoints
        if "/connect" in path:
            return "connect"

        # WebSocket connections
        if "/ws/" in path:
            return "websocket"

        # Default API rate limit
        return self.default_rule


class EnhancedAuthMiddleware(BaseHTTPMiddleware):
    """Enhanced authentication middleware with JWT and API key support"""

    def __init__(self, app, excluded_paths: list = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/healthcheck",
            "/ping",
            "/monitoring",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register",
        ]

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)

        # Skip authentication for CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_service = get_auth_service()
        user = None
        api_key = None

        try:
            # Try API key authentication first
            api_key_header = request.headers.get("X-API-Key")
            if api_key_header:
                auth_result = auth_service.authenticate_api_key(api_key_header)
                if auth_result:
                    user, api_key = auth_result
                    logger.info(
                        f"API key authentication successful for user {user.username}"
                    )

            # Try JWT authentication if no API key
            if not user:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]  # Remove "Bearer " prefix
                    user = auth_service.verify_access_token(token)
                    logger.info(
                        f"JWT authentication successful for user {user.username}"
                    )

            if not user:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "AUTHENTICATION_REQUIRED",
                        "message": "Valid authentication credentials required",
                        "details": "Provide either X-API-Key header or Authorization: Bearer <token>",
                    },
                )

            # Add user and API key to request state
            request.state.user = user
            request.state.api_key = api_key

            # Check user permissions for the endpoint
            if not self.check_endpoint_permission(request, user, api_key):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "INSUFFICIENT_PERMISSIONS",
                        "message": "Insufficient permissions for this endpoint",
                    },
                )

            return await call_next(request)

        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {e}")
            return JSONResponse(
                status_code=401,
                content={"error": "AUTHENTICATION_FAILED", "message": str(e)},
            )
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "INTERNAL_ERROR",
                    "message": "Authentication service error",
                },
            )

    def check_endpoint_permission(
        self, request: Request, user: User, api_key: APIKey = None
    ) -> bool:
        """Check if user has permission for the endpoint"""
        path = request.url.path
        method = request.method

        # Admin users have access to everything
        if user.role.value == "admin":
            return True

        # Define endpoint permissions
        endpoint_permissions = {
            "/connect": "connect",
            "/disconnect": "connect",
            "/profile/": "read",
            "/profiles/revalidate": "write",
            "/status": "read",
            "/sessions": "read",
            "/cache/": "admin",
            "/metrics": "admin",
        }

        # Find matching permission
        required_permission = "read"  # default
        for endpoint, permission in endpoint_permissions.items():
            if path.startswith(endpoint):
                required_permission = permission
                break

        # Check permission
        auth_service = get_auth_service()
        return auth_service.check_permission(user, required_permission, api_key)


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Input validation and sanitization middleware"""

    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next):
        try:
            # Validate request size
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    RequestValidator.validate_request_size(size, self.max_request_size)
                except ValidationError as e:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "REQUEST_TOO_LARGE", "message": str(e)},
                    )

            # Validate content type for POST/PUT requests
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if content_type:
                    try:
                        RequestValidator.validate_content_type(content_type)
                    except ValidationError as e:
                        return JSONResponse(
                            status_code=415,
                            content={
                                "error": "UNSUPPORTED_MEDIA_TYPE",
                                "message": str(e),
                            },
                        )

            # Validate User-Agent
            user_agent = request.headers.get("user-agent", "")
            if user_agent:
                try:
                    RequestValidator.validate_user_agent(user_agent)
                except ValidationError:
                    logger.warning(f"Invalid user agent: {user_agent}")
                    # Don't block request, just log

            # Validate Referer if present
            referer = request.headers.get("referer")
            if referer:
                try:
                    # Allow requests from localhost for development
                    allowed_domains = ["localhost", "127.0.0.1", "example.com"]
                    RequestValidator.validate_referer(referer, allowed_domains)
                except ValidationError:
                    logger.warning(f"Invalid referer: {referer}")
                    # Don't block request, just log

            return await call_next(request)

        except Exception as e:
            logger.error(f"Input validation middleware error: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                },
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers middleware"""

    def __init__(self, app):
        super().__init__(app)
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value

        # Add correlation ID to response
        corr_id = correlation_id.get()
        if corr_id:
            response.headers["X-Correlation-ID"] = corr_id

        return response


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Security audit and logging middleware"""

    def __init__(self, app):
        super().__init__(app)
        self.suspicious_patterns = [
            "../",  # Path traversal
            "<script",  # XSS
            "javascript:",  # XSS
            "union select",  # SQL injection
            "drop table",  # SQL injection
            "exec(",  # Code injection
            "eval(",  # Code injection
        ]

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request details
        client_ip = self.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Check for suspicious patterns in URL and headers
        suspicious_activity = self.detect_suspicious_activity(request)

        if suspicious_activity:
            logger.warning(
                f"Suspicious activity detected from {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "path": str(request.url.path),
                    "method": request.method,
                    "suspicious_patterns": suspicious_activity,
                },
            )

        # Process request
        response = await call_next(request)

        # Log response details
        duration = time.time() - start_time

        logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                "client_ip": client_ip,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "user_agent": user_agent[:100] if user_agent else None,
            },
        )

        return response

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def detect_suspicious_activity(self, request: Request) -> list:
        """Detect suspicious patterns in request"""
        suspicious = []

        # Check URL path
        path = str(request.url.path).lower()
        for pattern in self.suspicious_patterns:
            if pattern in path:
                suspicious.append(f"URL: {pattern}")

        # Check query parameters
        query = str(request.url.query).lower()
        for pattern in self.suspicious_patterns:
            if pattern in query:
                suspicious.append(f"Query: {pattern}")

        # Check headers
        for header_name, header_value in request.headers.items():
            header_value_lower = header_value.lower()
            for pattern in self.suspicious_patterns:
                if pattern in header_value_lower:
                    suspicious.append(f"Header {header_name}: {pattern}")

        return suspicious
