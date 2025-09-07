"""
Authentication and Authorization Endpoints.

This module provides a comprehensive set of endpoints for managing user
authentication, registration, and API key access. It serves as the primary
interface for all security and access control operations within the Profile API.

Endpoints Provided:
- `/register`: Allows new users to create an account.
- `/login`: Authenticates users and provides JWT access and refresh tokens.
- `/refresh`: Enables token renewal using a valid refresh token.
- `/logout`: Invalidates a user's current session.
- `/me`: Retrieves the profile of the currently authenticated user.
- `/api-keys`: Manages the lifecycle of API keys, including creation, listing,
  and revocation.

Architectural Design:
- RESTful Principles: The endpoints follow RESTful conventions for resource
  management (e.g., POST for creation, GET for retrieval, DELETE for removal).
- Data Validation: Pydantic models (`RegisterRequest`, `LoginRequest`, etc.) are
  used for robust request validation and serialization.
- Dependency Injection: The `AuthService` and current user are injected into
  endpoint functions, ensuring a clean separation of concerns.
- Security: Rate limiting is applied to sensitive endpoints like login and
  registration to prevent abuse. Permissions are enforced to restrict access
  to administrative functionalities.
- Clear Responses: Endpoints return well-defined Pydantic models (`UserResponse`,
  `TokenResponse`, etc.), ensuring predictable and type-safe API responses.
"""

from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr

from core.auth import get_auth_service, User, UserRole, APIKey
from core.logging_config import get_logger, log_function_call
from core.exceptions import AuthenticationError, ValidationError
from core.rate_limiter import rate_limit_decorator

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response Models
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Optional[str] = "user"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CreateAPIKeyRequest(BaseModel):
    name: str
    permissions: List[str]
    expires_in_days: Optional[int] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse


class APIKeyResponse(BaseModel):
    key_id: str
    name: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    is_active: bool


class CreateAPIKeyResponse(BaseModel):
    api_key: str
    key_info: APIKeyResponse


# Dependency to get current user
def get_current_user(request: Request) -> User:
    """Get current authenticated user from request state"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user


def get_current_api_key(request: Request) -> Optional[APIKey]:
    """Get current API key from request state"""
    return getattr(request.state, "api_key", None)


@router.post("/register", response_model=UserResponse)
@log_function_call(logger)
@rate_limit_decorator("auth")
async def register_user(request: RegisterRequest):
    """Register a new user"""
    try:
        auth_service = get_auth_service()

        # Validate role
        try:
            role = UserRole(request.role.lower())
        except ValueError:
            raise ValidationError(
                "role",
                request.role,
                "Invalid role. Must be one of: admin, user, service, readonly",
            )

        # Only admins can create admin users
        if role == UserRole.ADMIN:
            raise ValidationError(
                "role", request.role, "Cannot create admin users through registration"
            )

        # Register user
        user = auth_service.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
            role=role,
        )

        logger.info(f"User registered successfully: {user.username}")

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
        )

    except (ValidationError, AuthenticationError) as e:
        logger.warning(f"User registration failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"User registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
@log_function_call(logger)
@rate_limit_decorator("auth")
async def login_user(request: LoginRequest):
    """Authenticate user and return tokens"""
    try:
        auth_service = get_auth_service()

        # Authenticate user
        user = auth_service.authenticate_user(request.username, request.password)
        if not user:
            raise AuthenticationError("Invalid username or password")

        # Create tokens
        tokens = auth_service.create_tokens(user)

        logger.info(f"User logged in successfully: {user.username}")

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role.value,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login,
            ),
        )

    except AuthenticationError as e:
        logger.warning(f"User login failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"User login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/refresh", response_model=Dict[str, str])
@log_function_call(logger)
async def refresh_access_token(
    request: RefreshTokenRequest, current_user: User = Depends(get_current_user)
):
    """Refresh access token using refresh token"""
    try:
        auth_service = get_auth_service()

        # Create new access token
        new_access_token = auth_service.jwt_manager.refresh_access_token(
            request.refresh_token, current_user
        )

        logger.info(f"Access token refreshed for user: {current_user.username}")

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": str(
                int(auth_service.jwt_manager.access_token_expire.total_seconds())
            ),
        }

    except AuthenticationError as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@router.post("/logout")
@log_function_call(logger)
async def logout_user(request: Request, current_user: User = Depends(get_current_user)):
    """Logout user and revoke token"""
    try:
        auth_service = get_auth_service()

        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            auth_service.revoke_token(token)

        logger.info(f"User logged out: {current_user.username}")

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/me", response_model=UserResponse)
@log_function_call(logger)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )


@router.post("/api-keys", response_model=CreateAPIKeyResponse)
@log_function_call(logger)
async def create_api_key(
    request: CreateAPIKeyRequest, current_user: User = Depends(get_current_user)
):
    """Create new API key for current user"""
    try:
        auth_service = get_auth_service()

        # Validate permissions
        valid_permissions = ["read", "write", "connect", "admin", "*"]
        for permission in request.permissions:
            if permission not in valid_permissions:
                raise ValidationError(
                    "permissions",
                    permission,
                    f"Invalid permission. Must be one of: {', '.join(valid_permissions)}",
                )

        # Create API key
        api_key, key_obj = auth_service.api_key_manager.generate_api_key(
            user_id=current_user.id,
            name=request.name,
            permissions=request.permissions,
            expires_in_days=request.expires_in_days,
        )

        logger.info(f"API key created for user {current_user.username}: {key_obj.name}")

        return CreateAPIKeyResponse(
            api_key=api_key,
            key_info=APIKeyResponse(
                key_id=key_obj.key_id,
                name=key_obj.name,
                permissions=key_obj.permissions,
                created_at=key_obj.created_at,
                expires_at=key_obj.expires_at,
                last_used=key_obj.last_used,
                is_active=key_obj.is_active,
            ),
        )

    except ValidationError as e:
        logger.warning(f"API key creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API key creation error: {e}")
        raise HTTPException(status_code=500, detail="API key creation failed")


@router.get("/api-keys", response_model=List[APIKeyResponse])
@log_function_call(logger)
async def list_api_keys(current_user: User = Depends(get_current_user)):
    """List all API keys for current user"""
    try:
        auth_service = get_auth_service()
        keys = auth_service.api_key_manager.list_user_keys(current_user.id)

        return [
            APIKeyResponse(
                key_id=key.key_id,
                name=key.name,
                permissions=key.permissions,
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_used=key.last_used,
                is_active=key.is_active,
            )
            for key in keys
        ]

    except Exception as e:
        logger.error(f"API key listing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.delete("/api-keys/{key_id}")
@log_function_call(logger)
async def revoke_api_key(key_id: str, current_user: User = Depends(get_current_user)):
    """Revoke an API key"""
    try:
        auth_service = get_auth_service()

        success = auth_service.api_key_manager.revoke_api_key(key_id, current_user.id)

        if not success:
            raise HTTPException(status_code=404, detail="API key not found")

        logger.info(f"API key revoked by user {current_user.username}: {key_id}")

        return {"message": "API key revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key revocation error: {e}")
        raise HTTPException(status_code=500, detail="API key revocation failed")
