"""
Custom Exception Classes for the Profile API.

This module defines a suite of custom exception classes to provide structured,
consistent, and informative error handling throughout the Profile API. Using
specific exceptions for different error scenarios allows for more precise error
logging, monitoring, and client-side handling.

Key Components:
- `ProfileAPIException`: The base exception class from which all other custom
  exceptions in this module inherit. It establishes a common structure for
  errors, including a message, an error code, and optional details.
- Specific Exception Classes: Each class represents a distinct type of error,
  such as `TikTokConnectionError`, `ProfileNotFoundError`, `ValidationError`,
  and `AuthenticationError`. This allows different error conditions to be
  handled differently by the application's error handling middleware.
- `to_http_exception`: A utility function that maps custom `ProfileAPIException`
  instances to FastAPI's `HTTPException`. This translation layer decouples the
  application's internal error representation from the HTTP response format.

Architectural Design:
- Hierarchy of Exceptions: The exceptions are organized in a clear hierarchy with
  `ProfileAPIException` at the root. This allows for flexible error handling,
  where specific errors can be caught and handled individually, or multiple
  related errors can be caught by handling a more general base class.
- Rich Error Information: Each exception carries a unique `error_code` and can
  hold a `details` dictionary, providing structured context that is invaluable
  for debugging and can be safely exposed to clients.
- Centralized Error Mapping: The `to_http_exception` function centralizes the logic
  for converting internal application errors into appropriate HTTP status codes
  and response bodies. This ensures consistency and simplifies the error
  handling middleware.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException


class ProfileAPIException(Exception):
    """Base exception class for Profile API"""

    def __init__(
        self,
        message: str,
        error_code: str = "PROFILE_API_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class TikTokConnectionError(ProfileAPIException):
    """Raised when TikTok connection fails"""

    def __init__(self, username: str, reason: str):
        super().__init__(
            f"Failed to connect to TikTok for user {username}: {reason}",
            "TIKTOK_CONNECTION_ERROR",
            {"username": username, "reason": reason},
        )


class ProfileNotFoundError(ProfileAPIException):
    """Raised when a user profile cannot be found"""

    def __init__(self, username: str):
        super().__init__(
            f"Profile not found for username: {username}",
            "PROFILE_NOT_FOUND",
            {"username": username},
        )


class AvatarProcessingError(ProfileAPIException):
    """Raised when avatar processing fails"""

    def __init__(self, username: str, reason: str):
        super().__init__(
            f"Avatar processing failed for {username}: {reason}",
            "AVATAR_PROCESSING_ERROR",
            {"username": username, "reason": reason},
        )


class DatabaseConnectionError(ProfileAPIException):
    """Raised when database operations fail"""

    def __init__(self, operation: str, reason: str):
        super().__init__(
            f"Database operation '{operation}' failed: {reason}",
            "DATABASE_ERROR",
            {"operation": operation, "reason": reason},
        )


class WebSocketConnectionError(ProfileAPIException):
    """Raised when WebSocket operations fail"""

    def __init__(self, session_id: str, reason: str):
        super().__init__(
            f"WebSocket error for session {session_id}: {reason}",
            "WEBSOCKET_ERROR",
            {"session_id": session_id, "reason": reason},
        )


class ValidationError(ProfileAPIException):
    """Raised when input validation fails"""

    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(
            f"Validation failed for field '{field}': {reason}",
            "VALIDATION_ERROR",
            {"field": field, "value": str(value), "reason": reason},
        )


class RateLimitExceededError(ProfileAPIException):
    """Raised when rate limits are exceeded"""

    def __init__(self, identifier: str, limit: int, window: str):
        super().__init__(
            f"Rate limit exceeded for {identifier}: {limit} requests per {window}",
            "RATE_LIMIT_EXCEEDED",
            {"identifier": identifier, "limit": limit, "window": window},
        )


class RateLimitError(ProfileAPIException):
    """Raised when rate limit is exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", details: Optional[Dict] = None
    ):
        super().__init__(message, details)
        self.status_code = 429


class CacheError(ProfileAPIException):
    """Raised when cache operations fail."""

    def __init__(
        self, message: str = "Cache operation failed", details: Optional[Dict] = None
    ):
        super().__init__(message, details)
        self.status_code = 500


class WebSocketError(ProfileAPIException):
    """WebSocket connection error"""

    status_code = 500


class AuthenticationError(ProfileAPIException):
    """Raised when authentication fails"""

    def __init__(self, reason: str):
        super().__init__(
            f"Authentication failed: {reason}",
            "AUTHENTICATION_ERROR",
            {"reason": reason},
        )


class ServiceUnavailableError(ProfileAPIException):
    """Raised when external services are unavailable"""

    def __init__(self, service: str, reason: str):
        super().__init__(
            f"Service '{service}' is unavailable: {reason}",
            "SERVICE_UNAVAILABLE",
            {"service": service, "reason": reason},
        )


def convert_to_http_exception(exception: ProfileAPIException) -> HTTPException:
    """Convert a ProfileAPIException to a FastAPI HTTPException"""
    return HTTPException(
        status_code=exception.status_code,
        detail={
            "error": exception.error_code,
            "message": str(exception),
            "details": exception.details,
        },
    )


def to_http_exception(exc: ProfileAPIException) -> HTTPException:
    """Convert ProfileAPIException to FastAPI HTTPException"""

    status_code_map = {
        "PROFILE_NOT_FOUND": 404,
        "VALIDATION_ERROR": 400,
        "AUTHENTICATION_ERROR": 401,
        "RATE_LIMIT_EXCEEDED": 429,
        "SERVICE_UNAVAILABLE": 503,
        "TIKTOK_CONNECTION_ERROR": 502,
        "DATABASE_ERROR": 500,
        "WEBSOCKET_ERROR": 500,
        "AVATAR_PROCESSING_ERROR": 500,
    }

    status_code = status_code_map.get(exc.error_code, 500)

    return HTTPException(
        status_code=status_code,
        detail={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )
