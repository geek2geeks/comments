"""
Input Validation and Sanitization Utilities.

This module provides a robust set of tools for validating and sanitizing user
input to enhance the security and reliability of the Profile API. It includes
validators for common data types and patterns, as well as mechanisms to protect
against common web vulnerabilities like SQL injection and Cross-Site Scripting (XSS).

Key Components:
- `InputValidator`: A static class containing a comprehensive suite of validation
  and sanitization methods for various data types, including strings, emails,
  usernames, URLs, and numbers. It also includes checks for dangerous patterns.
- `RequestValidator`: A class focused on validating components of an HTTP request,
  such as the content type, request size, and user agent.
- `ValidationError`: A custom exception that is raised when validation fails,
  providing clear and structured information about the error.
- Security Pattern Matching: The `InputValidator` includes regex patterns to
  detect and block potential SQL injection and XSS attacks, providing a critical
  layer of defense.

Architectural Design:
- Static Methods for Reusability: The use of static methods in `InputValidator`
  and `RequestValidator` makes the validation logic easy to call from anywhere
  in the application without needing to instantiate an object.
- Centralized Logic: All core validation logic is centralized in this module,
  ensuring that validation rules are applied consistently across the application.
- Defense in Depth: The validation and sanitization provided by this module are
  a key part of a defense-in-depth security strategy. By validating all input at
  the application layer, it reduces the risk of malicious data reaching
  downstream components like the database.
- Clarity and Specificity: The module provides specific validation functions for
  different types of data (e.g., `validate_email`, `validate_username`). This
  makes the code more readable and the validation rules more explicit.
"""

import re
import html
import json
from typing import Any, Dict, List, Callable
from urllib.parse import urlparse
import ipaddress

from core.logging_config import get_logger
from core.exceptions import ValidationError

logger = get_logger(__name__)


class InputValidator:
    """Comprehensive input validation and sanitization"""

    # Common regex patterns
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,30}$")
    SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]{8,64}$")
    API_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9]{32,128}$")

    # Dangerous patterns to detect
    SQL_INJECTION_PATTERNS = [
        re.compile(r"('|(\-\-)|(;)|(\||\|)|(\*|\*))", re.IGNORECASE),
        re.compile(
            r"(union|select|insert|delete|update|drop|create|alter|exec|execute)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(script|javascript|vbscript|onload|onerror|onclick)", re.IGNORECASE
        ),
    ]

    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    ]

    @staticmethod
    def sanitize_string(
        value: str, max_length: int = 1000, allow_html: bool = False
    ) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValidationError("input", value, "Must be a string")

        # Trim whitespace
        value = value.strip()

        # Check length
        if len(value) > max_length:
            raise ValidationError(
                "input", value, f"Must be no more than {max_length} characters"
            )

        # HTML escape if not allowing HTML
        if not allow_html:
            value = html.escape(value)

        # Check for dangerous patterns
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                logger.warning(
                    f"Potential SQL injection attempt detected: {value[:100]}"
                )
                raise ValidationError(
                    "input", value, "Contains potentially dangerous content"
                )

        if not allow_html:
            for pattern in InputValidator.XSS_PATTERNS:
                if pattern.search(value):
                    logger.warning(f"Potential XSS attempt detected: {value[:100]}")
                    raise ValidationError(
                        "input", value, "Contains potentially dangerous content"
                    )

        return value

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email address"""
        email = InputValidator.sanitize_string(email, max_length=254)

        if not InputValidator.EMAIL_PATTERN.match(email):
            raise ValidationError("email", email, "Invalid email format")

        return email.lower()

    @staticmethod
    def validate_username(username: str) -> str:
        """Validate username"""
        username = InputValidator.sanitize_string(username, max_length=30)

        if not InputValidator.USERNAME_PATTERN.match(username):
            raise ValidationError(
                "username",
                username,
                "Username must be 3-30 characters and contain only letters, numbers, dots, hyphens, and underscores",
            )

        return username

    @staticmethod
    def validate_session_id(session_id: str) -> str:
        """Validate session ID"""
        session_id = InputValidator.sanitize_string(session_id, max_length=64)

        if not InputValidator.SESSION_ID_PATTERN.match(session_id):
            raise ValidationError(
                "session_id",
                session_id,
                "Session ID must be 8-64 characters and contain only alphanumeric characters and hyphens",
            )

        return session_id

    @staticmethod
    def validate_api_key(api_key: str) -> str:
        """Validate API key"""
        api_key = InputValidator.sanitize_string(api_key, max_length=128)

        if not InputValidator.API_KEY_PATTERN.match(api_key):
            raise ValidationError(
                "api_key", api_key, "API key must be 32-128 alphanumeric characters"
            )

        return api_key

    @staticmethod
    def validate_url(url: str, allowed_schemes: List[str] = None) -> str:
        """Validate URL"""
        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]

        url = InputValidator.sanitize_string(url, max_length=2048)

        try:
            parsed = urlparse(url)

            if not parsed.scheme:
                raise ValidationError(
                    "url", url, "URL must include a scheme (http/https)"
                )

            if parsed.scheme not in allowed_schemes:
                raise ValidationError(
                    "url",
                    url,
                    f"URL scheme must be one of: {', '.join(allowed_schemes)}",
                )

            if not parsed.netloc:
                raise ValidationError("url", url, "URL must include a valid domain")

        except Exception as e:
            raise ValidationError("url", url, f"Invalid URL format: {str(e)}")

        return url

    @staticmethod
    def validate_ip_address(ip: str, allow_private: bool = True) -> str:
        """Validate IP address"""
        ip = InputValidator.sanitize_string(ip, max_length=45)  # IPv6 max length

        try:
            ip_obj = ipaddress.ip_address(ip)

            if not allow_private and ip_obj.is_private:
                raise ValidationError(
                    "ip_address", ip, "Private IP addresses are not allowed"
                )

            if ip_obj.is_loopback:
                logger.info(f"Loopback IP address detected: {ip}")

        except ValueError as e:
            raise ValidationError("ip_address", ip, f"Invalid IP address: {str(e)}")

        return ip

    @staticmethod
    def validate_json(data: str, max_size: int = 1024 * 1024) -> Dict[str, Any]:
        """Validate and parse JSON data"""
        if len(data) > max_size:
            raise ValidationError(
                "json", data[:100], f"JSON data too large (max {max_size} bytes)"
            )

        try:
            parsed = json.loads(data)
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError("json", data[:100], f"Invalid JSON format: {str(e)}")

    @staticmethod
    def validate_integer(value: Any, min_val: int = None, max_val: int = None) -> int:
        """Validate integer value"""
        try:
            if isinstance(value, str):
                value = int(value)
            elif not isinstance(value, int):
                raise ValueError("Not an integer")

            if min_val is not None and value < min_val:
                raise ValidationError("integer", value, f"Must be at least {min_val}")

            if max_val is not None and value > max_val:
                raise ValidationError("integer", value, f"Must be at most {max_val}")

            return value

        except (ValueError, TypeError) as e:
            raise ValidationError("integer", value, f"Invalid integer: {str(e)}")

    @staticmethod
    def validate_float(
        value: Any, min_val: float = None, max_val: float = None
    ) -> float:
        """Validate float value"""
        try:
            if isinstance(value, str):
                value = float(value)
            elif not isinstance(value, (int, float)):
                raise ValueError("Not a number")

            value = float(value)

            if min_val is not None and value < min_val:
                raise ValidationError("float", value, f"Must be at least {min_val}")

            if max_val is not None and value > max_val:
                raise ValidationError("float", value, f"Must be at most {max_val}")

            return value

        except (ValueError, TypeError) as e:
            raise ValidationError("float", value, f"Invalid number: {str(e)}")

    @staticmethod
    def validate_boolean(value: Any) -> bool:
        """Validate boolean value"""
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ("true", "1", "yes", "on"):
                return True
            elif lower_val in ("false", "0", "no", "off"):
                return False

        if isinstance(value, int):
            return bool(value)

        raise ValidationError("boolean", value, "Invalid boolean value")

    @staticmethod
    def validate_list(
        value: Any, item_validator: Callable = None, max_items: int = 100
    ) -> List[Any]:
        """Validate list value"""
        if not isinstance(value, list):
            raise ValidationError("list", value, "Must be a list")

        if len(value) > max_items:
            raise ValidationError(
                "list", value, f"List cannot have more than {max_items} items"
            )

        if item_validator:
            validated_items = []
            for i, item in enumerate(value):
                try:
                    validated_items.append(item_validator(item))
                except ValidationError as e:
                    raise ValidationError(
                        "list", value, f"Item {i}: {e.details['reason']}"
                    )
            return validated_items

        return value

    @staticmethod
    def validate_dict(
        value: Any, schema: Dict[str, Callable] = None, allow_extra: bool = True
    ) -> Dict[str, Any]:
        """Validate dictionary value against schema"""
        if not isinstance(value, dict):
            raise ValidationError("dict", value, "Must be a dictionary")

        if schema:
            validated = {}

            # Validate required fields
            for key, validator in schema.items():
                if key in value:
                    try:
                        validated[key] = validator(value[key])
                    except ValidationError as e:
                        raise ValidationError(
                            "dict", value, f"Field '{key}': {e.details['reason']}"
                        )
                else:
                    raise ValidationError(
                        "dict", value, f"Missing required field: {key}"
                    )

            # Handle extra fields
            if allow_extra:
                for key, val in value.items():
                    if key not in schema:
                        validated[key] = val
            else:
                extra_keys = set(value.keys()) - set(schema.keys())
                if extra_keys:
                    raise ValidationError(
                        "dict", value, f"Unexpected fields: {', '.join(extra_keys)}"
                    )

            return validated

        return value


class RequestValidator:
    """Request-specific validation"""

    @staticmethod
    def validate_content_type(
        content_type: str, allowed_types: List[str] = None
    ) -> str:
        """Validate request content type"""
        if allowed_types is None:
            allowed_types = [
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ]

        # Extract main content type (ignore charset, boundary, etc.)
        main_type = content_type.split(";")[0].strip().lower()

        if main_type not in allowed_types:
            raise ValidationError(
                "content_type",
                content_type,
                f"Content type must be one of: {', '.join(allowed_types)}",
            )

        return main_type

    @staticmethod
    def validate_request_size(
        content_length: int, max_size: int = 10 * 1024 * 1024
    ) -> int:
        """Validate request body size"""
        if content_length > max_size:
            raise ValidationError(
                "content_length",
                content_length,
                f"Request body too large (max {max_size} bytes)",
            )

        return content_length

    @staticmethod
    def validate_user_agent(user_agent: str, min_length: int = 10) -> str:
        """Validate user agent string"""
        user_agent = InputValidator.sanitize_string(user_agent, max_length=500)

        if len(user_agent) < min_length:
            logger.warning(f"Suspicious short user agent: {user_agent}")

        # Check for common bot patterns
        bot_patterns = ["bot", "crawler", "spider", "scraper"]
        if any(pattern in user_agent.lower() for pattern in bot_patterns):
            logger.info(f"Bot user agent detected: {user_agent}")

        return user_agent

    @staticmethod
    def validate_referer(referer: str, allowed_domains: List[str] = None) -> str:
        """Validate referer header"""
        if not referer:
            return referer

        referer = InputValidator.validate_url(referer)

        if allowed_domains:
            parsed = urlparse(referer)
            domain = parsed.netloc.lower()

            if not any(
                domain.endswith(allowed_domain) for allowed_domain in allowed_domains
            ):
                logger.warning(f"Request from unauthorized referer: {referer}")
                raise ValidationError(
                    "referer",
                    referer,
                    f"Referer domain not allowed. Allowed domains: {', '.join(allowed_domains)}",
                )

        return referer


# Validation decorators
def validate_input(**validators):
    """Decorator to validate function inputs"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Validate keyword arguments
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = validator(kwargs[param_name])
                    except ValidationError as e:
                        logger.warning(
                            f"Validation failed for parameter {param_name}: {e}"
                        )
                        raise

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Common validation functions for reuse
def validate_tiktok_username(username: str) -> str:
    """Validate TikTok username format"""
    username = InputValidator.sanitize_string(username, max_length=24)

    # TikTok usernames can contain letters, numbers, underscores, and periods
    # Must be 2-24 characters
    if not re.match(r"^[a-zA-Z0-9_.]{2,24}$", username):
        raise ValidationError(
            "tiktok_username",
            username,
            "TikTok username must be 2-24 characters and contain only letters, numbers, underscores, and periods",
        )

    return username


def validate_comment_text(text: str) -> str:
    """Validate comment text"""
    text = InputValidator.sanitize_string(text, max_length=500, allow_html=False)

    if len(text.strip()) == 0:
        raise ValidationError("comment_text", text, "Comment cannot be empty")

    return text
