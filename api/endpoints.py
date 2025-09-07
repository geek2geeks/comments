"""
API Endpoints for Profile & Engagement.

This module defines the core REST and WebSocket endpoints for the Profile &
Engagement API. It handles TikTok integration, profile management, and real-time
comment streaming.

Endpoints Provided:
- `/connect`: Initiates a connection to a TikTok user's live stream.
- `/disconnect`: Terminates a connection to a TikTok live stream.
- `/profile/{username}`: Retrieves a user's profile, including their avatar.
- `/profiles/revalidate`: Triggers a background revalidation of user profiles.
- `/status`: Provides the current status and statistics of the API.
- `/sessions`: Lists all active TikTok Live sessions.
- `/ws/comments/{session_id}`: WebSocket endpoint for streaming live comments.

Architectural Design:
- Separation of Concerns: REST and WebSocket endpoints are defined in separate
  routers (`router` and `websocket_router`) for clarity.
- Dependency Injection: Services like `ConnectionService` and `AvatarService` are
  injected into endpoint functions, promoting loose coupling and testability.
- Asynchronous Operations: All endpoints are `async` to handle I/O-bound tasks
  efficiently, such as network requests and database queries.
- Error Handling: Endpoints raise specific HTTP exceptions for different error
  scenarios, which are then handled by the global error handling middleware.
- Caching: The `/profile` endpoint leverages caching to reduce latency and
  minimize external API calls.
"""

import logging
import asyncio
from typing import List, Dict
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from services.avatar_service import AvatarService
from services.connection_service import ConnectionService
from core.models import Comment
from core.database import get_database_info
from core.logging_config import log_function_call
from core.exceptions import TikTokConnectionError, ValidationError, RateLimitError
from core.cache import get_cache
from core.performance import get_metrics_collector, timed, async_timer
from fastapi import Depends
from .dependencies import get_avatar_service, get_connection_service

logger = logging.getLogger(__name__)


router = APIRouter(tags=["Profile Management"])
websocket_router = APIRouter(tags=["WebSocket Communication"])


# Request/Response Models
class ConnectRequest(BaseModel):
    session_id: str
    username: str


class DisconnectRequest(BaseModel):
    session_id: str


class ProfileResponse(BaseModel):
    username: str
    nickname: str
    avatar_url: str
    avatar_data_url: str
    source: str
    cached_at: str


class RevalidateRequest(BaseModel):
    usernames: List[str]


class RevalidateResponse(BaseModel):
    results: Dict[str, bool]
    total_requested: int
    successful: int
    failed: int


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session {session_id}")

    async def send_comment(self, session_id: str, comment: Comment):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(
                    {"type": "comment", "data": comment.dict()}
                )
            except Exception as e:
                logger.error(f"Error sending comment to session {session_id}: {e}")
                self.disconnect(session_id)


websocket_manager = ConnectionManager()


# REST Endpoints
@router.post("/connect")
@log_function_call(logger)
@timed("connect_endpoint")
async def connect_to_tiktok(
    request: ConnectRequest,
    conn_svc: ConnectionService = Depends(get_connection_service),
):
    """Start a TikTok listener for a given session_id and username"""
    cache = get_cache()
    metrics = get_metrics_collector()

    # Check cache for recent connection attempts
    cache_key = f"connection_attempt:{request.session_id}:{request.username}"
    recent_attempt = await cache.get(cache_key)

    if recent_attempt and recent_attempt.get("status") == "failed":
        logger.warning(
            f"Recent failed connection attempt for {request.username}, rate limiting",
            extra={
                "session_id": request.session_id,
                "username": request.username,
                "cache_hit": True,
            },
        )
        metrics.increment_counter(
            "connection_rate_limited", tags={"username": request.username}
        )
        raise RateLimitError(
            "Too many recent connection attempts. Please try again later."
        )

    try:
        async with async_timer(
            "connection_time", metrics, {"username": request.username}
        ):
            logger.info(
                f"Connect request: session={request.session_id}, username={request.username}"
            )

            # Create callback to send comments via WebSocket
            def comment_callback(comment: Comment):
                asyncio.create_task(
                    websocket_manager.send_comment(request.session_id, comment)
                )
                metrics.increment_counter(
                    "comments_received", tags={"username": request.username}
                )

            # Start the stream
            success = await conn_svc.start_stream(
                request.session_id, request.username, comment_callback
            )

            if success:
                # Cache successful connection
                success_info = {
                    "status": "success",
                    "session_id": request.session_id,
                    "username": request.username,
                    "connected_at": asyncio.get_event_loop().time(),
                }
                await cache.set(cache_key, success_info, ttl=300)

                logger.info(
                    f"Successfully connected to @{request.username}",
                    extra={
                        "session_id": request.session_id,
                        "username": request.username,
                        "action": "connect_success",
                    },
                )

                metrics.increment_counter(
                    "connection_attempts",
                    tags={"username": request.username, "result": "success"},
                )

                return {
                    "status": "success",
                    "session_id": request.session_id,
                    "username": request.username,
                    "message": f"Connected to @{request.username}",
                }
            else:
                raise TikTokConnectionError(
                    f"Failed to connect to @{request.username}. User may not be live."
                )

    except ValidationError:
        raise
    except TikTokConnectionError:
        raise
    except Exception as e:
        # Cache failed attempt
        failed_info = {
            "status": "failed",
            "session_id": request.session_id,
            "username": request.username,
            "error": str(e),
            "failed_at": asyncio.get_event_loop().time(),
        }
        await cache.set(cache_key, failed_info, ttl=300)

        metrics.increment_counter(
            "connection_attempts",
            tags={"username": request.username, "result": "failed"},
        )

        logger.error(
            f"Unexpected error connecting to TikTok: {e}",
            extra={
                "session_id": request.session_id,
                "username": request.username,
                "action": "connect_error",
            },
            exc_info=True,
        )
        raise TikTokConnectionError("An unexpected error occurred while connecting")


@router.post("/disconnect")
@log_function_call(logger)
async def disconnect_from_tiktok(
    request: DisconnectRequest,
    conn_svc: ConnectionService = Depends(get_connection_service),
):
    """Stop the listener for a given session_id"""
    try:
        # Validate input
        if not request.session_id:
            raise ValidationError("Session ID is required")

        logger.info(
            f"Disconnect request: session={request.session_id}",
            extra={"session_id": request.session_id, "action": "disconnect_request"},
        )

        success = await conn_svc.stop_stream(request.session_id)

        # Also disconnect WebSocket if connected
        websocket_manager.disconnect(request.session_id)

        logger.info(
            f"Disconnect completed for session {request.session_id}",
            extra={"session_id": request.session_id, "action": "disconnect_success"},
        )

        return {
            "status": "success" if success else "warning",
            "session_id": request.session_id,
            "message": "Disconnected successfully"
            if success
            else "No active connection found",
        }

    except ValidationError:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error disconnecting: {e}",
            extra={"session_id": request.session_id, "action": "disconnect_error"},
            exc_info=True,
        )
        raise TikTokConnectionError("An unexpected error occurred while disconnecting")


@router.get("/profile/{username}", response_model=ProfileResponse)
async def get_profile(
    username: str, avatar_svc: AvatarService = Depends(get_avatar_service)
):
    """Retrieve a user's profile (avatar, nickname) from cache or fetch new"""
    try:
        logger.info(f"Profile request for: {username}")

        profile = await avatar_svc.get_user_profile(username)

        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile not found for @{username}"
            )

        return ProfileResponse(
            username=profile.username,
            nickname=profile.nickname or username,
            avatar_url=profile.avatar_url or "",
            avatar_data_url=profile.avatar_data_url or "",
            source=profile.source or "unknown",
            cached_at=profile.last_checked_at.isoformat()
            if profile.last_checked_at
            else "",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/revalidate", response_model=RevalidateResponse)
async def revalidate_profiles(
    request: RevalidateRequest, avatar_svc: AvatarService = Depends(get_avatar_service)
):
    """Trigger background revalidation of user profiles"""
    try:
        logger.info(f"Revalidate request for {len(request.usernames)} users")

        results = await avatar_svc.revalidate_profiles(request.usernames)

        successful = sum(1 for success in results.values() if success)
        failed = len(request.usernames) - successful

        return RevalidateResponse(
            results=results,
            total_requested=len(request.usernames),
            successful=successful,
            failed=failed,
        )

    except Exception as e:
        logger.error(f"Error revalidating profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Status and Health Endpoints
@router.get("/status")
async def get_api_status(
    conn_svc: ConnectionService = Depends(get_connection_service),
    avatar_svc: AvatarService = Depends(get_avatar_service),
):
    """Get API status and statistics"""
    try:
        connection_stats = conn_svc.get_connection_stats()
        cache_stats = await avatar_svc.get_cache_stats()
        db_info = await get_database_info()

        return {
            "status": "healthy",
            "service": "Profile & Engagement API",
            "connections": connection_stats,
            "cache": cache_stats,
            "database": db_info,
            "websockets": {
                "active_connections": len(websocket_manager.active_connections),
                "session_ids": list(websocket_manager.active_connections.keys()),
            },
        }

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_active_sessions(
    conn_svc: ConnectionService = Depends(get_connection_service),
):
    """Get information about active TikTok Live sessions"""
    try:
        return conn_svc.get_active_sessions()
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket Endpoint
@websocket_router.websocket("/ws/comments/{session_id}")
async def websocket_comments(
    websocket: WebSocket,
    session_id: str,
    api_key: str = Query(..., alias="api_key"),
    conn_svc: ConnectionService = Depends(get_connection_service),
):
    """Stream comments for an active session via WebSocket"""
    try:
        # Verify API key before accepting WebSocket connection
        import os

        expected_key = os.getenv("API_KEY")
        logger.info(
            f"WebSocket connection attempt for session {session_id} with api_key: {api_key[:10]}..."
        )
        logger.info(
            f"Expected API key: {expected_key[:10] if expected_key else 'None'}..."
        )

        if expected_key is None:
            logger.error("API_KEY environment variable not set")
            await websocket.close(code=4003, reason="Server configuration error")
            return

        if api_key != expected_key:
            logger.warning(
                f"WebSocket authentication failed for session {session_id}. Provided: {api_key}, Expected: {expected_key}"
            )
            await websocket.close(code=4001, reason="Invalid API Key")
            return

        # Accept the WebSocket connection
        await websocket_manager.connect(websocket, session_id)

        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "session_id": session_id,
                "message": f"WebSocket connected for session {session_id}",
            }
        )

        try:
            # Keep connection alive and handle client messages
            while True:
                # Wait for client messages (like ping/heartbeat)
                try:
                    data = await websocket.receive_json()

                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif data.get("type") == "status":
                        # Send connection status
                        is_connected = conn_svc.is_connected(session_id)
                        await websocket.send_json(
                            {
                                "type": "status_response",
                                "session_id": session_id,
                                "tiktok_connected": is_connected,
                            }
                        )

                except asyncio.TimeoutError:
                    # No message received, continue waiting
                    continue

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        finally:
            websocket_manager.disconnect(session_id)

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        if session_id in websocket_manager.active_connections:
            websocket_manager.disconnect(session_id)


# Utility Endpoints
@router.post("/cache/clear-expired")
async def clear_expired_cache(avatar_svc: AvatarService = Depends(get_avatar_service)):
    """Clear expired profiles from cache"""
    try:
        count = await avatar_svc.clear_expired_profiles()
        return {
            "status": "success",
            "cleared_profiles": count,
            "message": f"Cleared {count} expired profiles",
        }
    except Exception as e:
        logger.error(f"Error clearing expired cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/cleanup")
async def cleanup_disconnected_sessions(
    conn_svc: ConnectionService = Depends(get_connection_service),
):
    """Clean up disconnected TikTok sessions"""
    try:
        count = await conn_svc.cleanup_disconnected_sessions()
        return {
            "status": "success",
            "cleaned_sessions": count,
            "message": f"Cleaned up {count} disconnected sessions",
        }
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
