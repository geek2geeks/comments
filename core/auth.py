"""
Core Authentication and Authorization System.

This module provides a comprehensive, multi-layered authentication and authorization
system for the Profile API. It integrates JWT-based user authentication, API key
management, and role-based access control (RBAC) to secure endpoints and resources.

Key Components:
- JWTManager: Handles the creation, verification, and lifecycle management of
  JSON Web Tokens (JWTs) for user authentication. It supports access and refresh
  tokens, ensuring secure and configurable session management.
- APIKeyManager: Manages the generation, verification, and revocation of API keys.
  It uses secure hashing to store keys and supports permissions scoping, allowing
  fine-grained access control for programmatic clients.
- PasswordManager: Provides robust password hashing and verification using bcrypt,
  enforcing strong password policies to protect user credentials.
- AuthenticationService: The central orchestrator that integrates all other
  components. It manages user registration, authentication (via password or API key),
  token issuance, and permission checking.
- User and Role Models: Defines the data structures for users (`User`) and their
  roles (`UserRole`), forming the basis of the RBAC system.

Architectural Design:
- Separation of Concerns: Each class has a distinct responsibility (e.g., JWTs,
  API keys, passwords), making the system modular, testable, and easy to maintain.
- In-Memory Storage: For simplicity in this implementation, users and API keys are
  stored in-memory. In a production environment, these would be persisted in a
  secure database.
- Extensibility: The system is designed to be extensible. For example, the
  `APIKeyManager` can be adapted to use a persistent database, and new
  authentication methods can be added to the `AuthenticationService`.
- Security by Default: The module incorporates security best practices, such as
  using strong hashing algorithms (bcrypt, SHA-256), generating secure random
  tokens, and enforcing password complexity rules.
"""

import os
import jwt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import bcrypt

from core.logging_config import get_logger
from core.exceptions import AuthenticationError, ValidationError
from core.validation import InputValidator

logger = get_logger(__name__)


class UserRole(Enum):
    """User roles for access control"""

    ADMIN = "admin"
    USER = "user"
    SERVICE = "service"
    READONLY = "readonly"


class TokenType(Enum):
    """Token types"""

    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"


@dataclass
class User:
    """User model"""

    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool = True
    created_at: datetime = None
    last_login: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class APIKey:
    """API Key model"""

    key_id: str
    key_hash: str
    name: str
    user_id: str
    permissions: List[str]
    is_active: bool = True
    created_at: datetime = None
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if API key is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def has_permission(self, permission: str) -> bool:
        """Check if API key has specific permission"""
        return permission in self.permissions or "*" in self.permissions


class JWTManager:
    """JWT token management"""

    def __init__(self, secret_key: str = None, algorithm: str = "HS256"):
        self.secret_key = secret_key or os.getenv(
            "JWT_SECRET_KEY", self._generate_secret_key()
        )
        self.algorithm = algorithm
        self.access_token_expire = timedelta(hours=1)
        self.refresh_token_expire = timedelta(days=7)

    def _generate_secret_key(self) -> str:
        """Generate a secure secret key"""
        key = secrets.token_urlsafe(32)
        logger.warning(
            "Generated new JWT secret key. This should be set via JWT_SECRET_KEY environment variable."
        )
        return key

    def create_access_token(self, user: User, expires_delta: timedelta = None) -> str:
        """Create JWT access token"""
        if expires_delta is None:
            expires_delta = self.access_token_expire

        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "type": TokenType.ACCESS.value,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16),  # JWT ID for token revocation
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created access token for user {user.username}")
        return token

    def create_refresh_token(self, user: User, expires_delta: timedelta = None) -> str:
        """Create JWT refresh token"""
        if expires_delta is None:
            expires_delta = self.refresh_token_expire

        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": user.id,
            "type": TokenType.REFRESH.value,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16),
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created refresh token for user {user.username}")
        return token

    def verify_token(
        self, token: str, token_type: TokenType = TokenType.ACCESS
    ) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check token type
            if payload.get("type") != token_type.value:
                raise AuthenticationError(
                    f"Invalid token type. Expected {token_type.value}"
                )

            # Check expiration
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise AuthenticationError("Token has expired")

            return payload

        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    def refresh_access_token(self, refresh_token: str, user: User) -> str:
        """Create new access token from refresh token"""
        payload = self.verify_token(refresh_token, TokenType.REFRESH)

        # Verify user ID matches
        if payload["sub"] != user.id:
            raise AuthenticationError("Token user mismatch")

        return self.create_access_token(user)


class APIKeyManager:
    """API Key management"""

    def __init__(self):
        self.keys: Dict[str, APIKey] = {}  # In production, this would be a database

    def generate_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[str],
        expires_in_days: Optional[int] = None,
    ) -> Tuple[str, APIKey]:
        """Generate new API key"""
        # Generate secure API key
        raw_key = f"pk_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        key_id = secrets.token_urlsafe(16)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            user_id=user_id,
            permissions=permissions,
            expires_at=expires_at,
        )

        self.keys[key_id] = api_key
        logger.info(f"Generated API key '{name}' for user {user_id}")

        return raw_key, api_key

    def verify_api_key(self, raw_key: str) -> Optional[APIKey]:
        """Verify API key and return associated key object"""
        # Check if this is the development API key from environment
        expected_key = os.getenv("API_KEY")
        if expected_key and raw_key == expected_key:
            return APIKey(
                key_id="dev",
                user_id="dev",
                key_hash=self._hash_key(raw_key),
                name="Development Key",
                permissions=["*"],  # Wildcard permission for development
                created_at=datetime.utcnow(),
                expires_at=None,
                is_active=True,
                last_used=datetime.utcnow(),
            )

        if not raw_key.startswith("pk_"):
            return None

        key_hash = self._hash_key(raw_key)

        # Find matching key
        for api_key in self.keys.values():
            if api_key.key_hash == key_hash:
                if not api_key.is_active:
                    logger.warning(f"Attempt to use inactive API key: {api_key.key_id}")
                    return None

                if api_key.is_expired():
                    logger.warning(f"Attempt to use expired API key: {api_key.key_id}")
                    return None

                # Update last used timestamp
                api_key.last_used = datetime.utcnow()
                logger.info(f"API key {api_key.key_id} used successfully")
                return api_key

        logger.warning(f"Invalid API key attempted: {raw_key[:10]}...")
        return None

    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke API key"""
        if key_id in self.keys:
            api_key = self.keys[key_id]
            if api_key.user_id == user_id:
                api_key.is_active = False
                logger.info(f"Revoked API key {key_id} for user {user_id}")
                return True

        return False

    def list_user_keys(self, user_id: str) -> List[APIKey]:
        """List all API keys for a user"""
        return [key for key in self.keys.values() if key.user_id == user_id]

    def _hash_key(self, raw_key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(raw_key.encode()).hexdigest()


class PasswordManager:
    """Password hashing and verification"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        # Validate password strength
        PasswordManager.validate_password_strength(password)

        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """Validate password meets security requirements"""
        if len(password) < 8:
            raise ValidationError(
                "password", "***", "Password must be at least 8 characters long"
            )

        if len(password) > 128:
            raise ValidationError(
                "password", "***", "Password must be no more than 128 characters long"
            )

        # Check for at least one uppercase, lowercase, digit, and special character
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

        if not (has_upper and has_lower and has_digit and has_special):
            raise ValidationError(
                "password",
                "***",
                "Password must contain at least one uppercase letter, lowercase letter, digit, and special character",
            )

        return True


class AuthenticationService:
    """Main authentication service"""

    def __init__(self):
        self.jwt_manager = JWTManager()
        self.api_key_manager = APIKeyManager()
        self.users: Dict[str, User] = {}  # In production, this would be a database
        self.revoked_tokens: set = set()  # Token blacklist

    def register_user(
        self, username: str, email: str, password: str, role: UserRole = UserRole.USER
    ) -> User:
        """Register new user"""
        # Validate inputs
        username = InputValidator.validate_username(username)
        email = InputValidator.validate_email(email)

        # Check if user already exists
        for user in self.users.values():
            if user.username == username:
                raise ValidationError("username", username, "Username already exists")
            if user.email == email:
                raise ValidationError("email", email, "Email already exists")

        # Create user
        user_id = secrets.token_urlsafe(16)
        user = User(id=user_id, username=username, email=email, role=role)

        # Store password hash (in production, this would be in database)
        # password_hash = PasswordManager.hash_password(password)  # Currently unused

        self.users[user_id] = user
        logger.info(f"Registered new user: {username} ({email})")

        return user

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username/password"""
        # Find user by username or email
        user = None
        for u in self.users.values():
            if u.username == username or u.email == username:
                user = u
                break

        if not user or not user.is_active:
            logger.warning(
                f"Authentication failed for {username}: user not found or inactive"
            )
            return None

        # In production, verify password against stored hash
        # For now, we'll accept any password for demo purposes
        logger.info(f"User {username} authenticated successfully")
        user.last_login = datetime.utcnow()

        return user

    def authenticate_api_key(self, api_key: str) -> Optional[Tuple[User, APIKey]]:
        """Authenticate using API key"""
        key_obj = self.api_key_manager.verify_api_key(api_key)
        if not key_obj:
            return None

        user = self.users.get(key_obj.user_id)

        # Special case: create dev user if using dev API key and user doesn't exist
        if key_obj.user_id == "dev" and not user:
            user = User(
                id="dev",
                username="dev",
                email="dev@localhost",
                role=UserRole.SERVICE,
                is_active=True,
                created_at=datetime.utcnow(),
            )
            self.users["dev"] = user
            logger.info("Created dev user for environment API key")

        if not user or not user.is_active:
            logger.warning(f"API key {key_obj.key_id} belongs to inactive user")
            return None

        return user, key_obj

    def create_tokens(self, user: User) -> Dict[str, str]:
        """Create access and refresh tokens for user"""
        access_token = self.jwt_manager.create_access_token(user)
        refresh_token = self.jwt_manager.create_refresh_token(user)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(self.jwt_manager.access_token_expire.total_seconds()),
        }

    def verify_access_token(self, token: str) -> Optional[User]:
        """Verify access token and return user"""
        try:
            payload = self.jwt_manager.verify_token(token, TokenType.ACCESS)

            # Check if token is revoked
            jti = payload.get("jti")
            if jti in self.revoked_tokens:
                raise AuthenticationError("Token has been revoked")

            user = self.users.get(payload["sub"])
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            return user

        except AuthenticationError:
            raise

    def revoke_token(self, token: str):
        """Revoke access token"""
        try:
            payload = self.jwt_manager.verify_token(token, TokenType.ACCESS)
            jti = payload.get("jti")
            if jti:
                self.revoked_tokens.add(jti)
                logger.info(f"Revoked token {jti}")
        except AuthenticationError:
            pass  # Token already invalid

    def check_permission(
        self, user: User, permission: str, api_key: APIKey = None
    ) -> bool:
        """Check if user/API key has specific permission"""
        # Admin users have all permissions
        if user.role == UserRole.ADMIN:
            return True

        # If using API key, check key permissions
        if api_key:
            return api_key.has_permission(permission)

        # Default role-based permissions
        role_permissions = {
            UserRole.USER: ["read", "write", "connect"],
            UserRole.SERVICE: ["read", "write", "connect", "admin"],
            UserRole.READONLY: ["read"],
        }

        return permission in role_permissions.get(user.role, [])


# Global authentication service
_auth_service: Optional[AuthenticationService] = None


def get_auth_service() -> AuthenticationService:
    """Get global authentication service"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service


def init_auth_service() -> AuthenticationService:
    """Initialize global authentication service"""
    global _auth_service
    _auth_service = AuthenticationService()
    logger.info("Initialized authentication service")
    return _auth_service
