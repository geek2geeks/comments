"""
TikTok Live Connection Management Service.

This module provides the `ConnectionService`, which is responsible for managing
active connections to TikTok Live streams. It handles the lifecycle of these
connections, including starting, stopping, and monitoring them.

Key Components:
- `ConnectionService`: The central service class that manages a dictionary of
  active TikTok Live listeners. Each listener is associated with a unique
  `session_id`.
- `CommentProvider`: The service interacts with `CommentProvider` instances
  (specifically, `TikTokLiveProvider`) to handle the low-level details of
  connecting to TikTok and receiving comments.
- Session Management: The service maintains the state of each active session,
  including the listener object and the callback function used to process
  incoming comments.

Architectural Design:
- Facade Pattern: The `ConnectionService` acts as a facade, providing a simple
  and clean interface (`start_stream`, `stop_stream`) for the rest of the
  application to interact with the more complex underlying TikTok connection
  providers.
- In-Memory State: The service manages the state of active connections in
  memory. This is suitable for a single-instance deployment. In a distributed
  environment, this state would need to be externalized to a shared store like
  Redis.
- Callback-Based Architecture: The service uses a callback mechanism to handle
  incoming comments. When a comment is received by a listener, it invokes the
  callback provided by the client (in this case, the API endpoint), which then
  forwards the comment to the appropriate WebSocket connection.
- Separation of Concerns: The service separates the concern of managing
  connection lifecycles from the concern of processing the data that comes from
  those connections. The service manages the connections, while the API
  endpoints and their clients handle the comment data.
"""

import logging
from typing import Dict, Callable, Any
from providers.comment_provider import CommentProvider, TikTokLiveProvider
from core.models import Comment

logger = logging.getLogger(__name__)


class ConnectionService:
    """Service that manages active TikTok Live connections"""

    def __init__(self):
        """Initialize with empty connections dictionary"""
        # Maps session_id to active CommentProvider
        self.active_listeners: Dict[str, CommentProvider] = {}

        # Maps session_id to callback function for comments
        self.session_callbacks: Dict[str, Callable[[Comment], None]] = {}

    async def start_stream(
        self, session_id: str, username: str, callback: Callable[[Comment], None]
    ) -> bool:
        """
        Start a TikTok listener for a given session and username.

        Args:
            session_id: Unique session identifier
            username: TikTok username to listen to
            callback: Function to call when comments are received

        Returns:
            bool: True if connection started successfully
        """
        try:
            # Check if session already has an active listener
            if session_id in self.active_listeners:
                logger.warning(f"Session {session_id} already has active listener")
                await self.stop_stream(session_id)  # Clean up first

            logger.info(f"Starting stream for session {session_id}, user @{username}")

            # Create new TikTok provider
            provider = TikTokLiveProvider()

            # Store callback for this session
            self.session_callbacks[session_id] = callback

            # Create wrapped callback that includes session context
            def session_callback(comment: Comment):
                try:
                    if session_id in self.session_callbacks:
                        self.session_callbacks[session_id](comment)
                except Exception as e:
                    logger.error(f"Error in session callback for {session_id}: {e}")

            # Start listening
            success = await provider.start_listening(username, session_callback)

            if success:
                # Store the active listener
                self.active_listeners[session_id] = provider
                logger.info(f"Successfully started stream for session {session_id}")
                return True
            else:
                # Clean up on failure
                if session_id in self.session_callbacks:
                    del self.session_callbacks[session_id]
                logger.error(f"Failed to start stream for session {session_id}")
                return False

        except Exception as e:
            logger.error(f"Error starting stream for session {session_id}: {e}")
            # Clean up on error
            if session_id in self.session_callbacks:
                del self.session_callbacks[session_id]
            return False

    async def stop_stream(self, session_id: str) -> bool:
        """
        Stop the listener for a given session.

        Args:
            session_id: Session identifier to stop

        Returns:
            bool: True if stopped successfully
        """
        try:
            if session_id not in self.active_listeners:
                logger.warning(f"No active listener found for session {session_id}")
                return False

            logger.info(f"Stopping stream for session {session_id}")

            # Get the listener
            listener = self.active_listeners[session_id]

            # Stop the listener
            await listener.stop_listening()

            # Clean up
            del self.active_listeners[session_id]
            if session_id in self.session_callbacks:
                del self.session_callbacks[session_id]

            logger.info(f"Successfully stopped stream for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping stream for session {session_id}: {e}")
            return False

    def is_connected(self, session_id: str) -> bool:
        """
        Check if a session has an active connection.

        Args:
            session_id: Session identifier to check

        Returns:
            bool: True if session is connected
        """
        if session_id not in self.active_listeners:
            return False

        listener = self.active_listeners[session_id]
        return listener.is_connected()

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all active sessions.

        Returns:
            Dict mapping session_id to session info
        """
        result = {}

        for session_id, listener in self.active_listeners.items():
            result[session_id] = {
                "session_id": session_id,
                "connected": listener.is_connected(),
                "username": getattr(listener, "username", "unknown"),
                "provider_type": listener.__class__.__name__,
            }

        return result

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Dictionary with connection stats
        """
        total_sessions = len(self.active_listeners)
        connected_sessions = sum(
            1 for listener in self.active_listeners.values() if listener.is_connected()
        )

        return {
            "total_sessions": total_sessions,
            "connected_sessions": connected_sessions,
            "disconnected_sessions": total_sessions - connected_sessions,
            "active_session_ids": list(self.active_listeners.keys()),
        }

    async def cleanup_disconnected_sessions(self) -> int:
        """
        Clean up sessions that are no longer connected.

        Returns:
            Number of sessions cleaned up
        """
        disconnected_sessions = []

        # Find disconnected sessions
        for session_id, listener in self.active_listeners.items():
            if not listener.is_connected():
                disconnected_sessions.append(session_id)

        # Clean them up
        cleaned_count = 0
        for session_id in disconnected_sessions:
            try:
                await self.stop_stream(session_id)
                cleaned_count += 1
                logger.info(f"Cleaned up disconnected session {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")

        return cleaned_count

    async def stop_all_streams(self) -> int:
        """
        Stop all active streams (useful for shutdown).

        Returns:
            Number of streams stopped
        """
        session_ids = list(self.active_listeners.keys())
        stopped_count = 0

        for session_id in session_ids:
            try:
                await self.stop_stream(session_id)
                stopped_count += 1
            except Exception as e:
                logger.error(f"Error stopping session {session_id}: {e}")

        logger.info(f"Stopped {stopped_count} active streams")
        return stopped_count
