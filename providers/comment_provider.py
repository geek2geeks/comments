"""
Comment Provider Classes

Refactored TikTok Live comment capture logic into clean provider classes.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Callable
from core.models import Comment

logger = logging.getLogger(__name__)

# Debug logger for detailed TikTok debugging
debug_logger = logging.getLogger("tiktok_debug")
debug_logger.setLevel(logging.DEBUG)


class CommentProvider(ABC):
    """Abstract base class for comment providers"""

    @abstractmethod
    async def start_listening(
        self, username: str, callback: Callable[[Comment], None]
    ) -> bool:
        """Start listening for comments from a user's live stream"""
        pass

    @abstractmethod
    async def stop_listening(self) -> None:
        """Stop listening for comments"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if provider is connected"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier for this provider"""
        pass


class TikTokLiveProvider(CommentProvider):
    """TikTok Live comment provider using TikTokLive library"""

    def __init__(self):
        self.username = None
        self.callback = None
        self._client = None
        self._running = False
        self._connected = False
        self._connect_task = None

    @property
    def source_name(self) -> str:
        return "tiktok"

    async def start_listening(
        self, username: str, callback: Callable[[Comment], None]
    ) -> bool:
        """Start listening for TikTok Live comments"""
        self.username = username.lstrip("@")
        self.callback = callback

        if self._running:
            logger.warning(f"TikTok listener already running for @{self.username}")
            return True

        logger.info(f"Starting TikTok Live listener for @{self.username}")

        try:
            # Import TikTok Live library
            from TikTokLive import TikTokLiveClient
            from TikTokLive.client.logger import LogLevel

            # Create client
            self._client = TikTokLiveClient(unique_id=f"@{self.username}")
            self._client.logger.setLevel(LogLevel.INFO.value)

            # Set up event handlers
            self._setup_event_handlers()

            # Check if user is live
            is_live = await self._client.is_live()
            if not is_live:
                logger.error(f"User @{self.username} is not currently live")
                return False

            logger.info(f"User @{self.username} is live! Starting connection...")

            # Start connection
            self._running = True
            self._connect_task = asyncio.create_task(self._client.connect())

            # Give connection time to establish
            await asyncio.sleep(3)

            logger.info(f"Connection process initiated for @{self.username}")
            return True

        except ImportError as e:
            logger.error(f"TikTokLive library not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error starting TikTok listener: {e}")
            return False

    def _setup_event_handlers(self):
        """Set up TikTok Live event handlers"""
        from TikTokLive.events import ConnectEvent, CommentEvent, DisconnectEvent

        @self._client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            logger.info(
                f"Connected to @{event.unique_id}! Room ID: {self._client.room_id}"
            )
            self._connected = True

        @self._client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            try:
                username = getattr(event.user, "unique_id", "Unknown")
                display_name = getattr(event.user, "nickname", username)
                text = getattr(event, "comment", "").strip()

                if not text:
                    return

                # Create Comment object
                comment = Comment(
                    username=username,
                    text=text,
                    timestamp_ms=int(time.time() * 1000),
                    source=self.source_name,
                )

                logger.info(
                    f"Comment from @{username}: {text[:50]}{'...' if len(text) > 50 else ''}"
                )

                # Call callback with Comment object
                if self.callback:
                    try:
                        self.callback(comment)
                    except Exception as cb_error:
                        logger.error(f"Callback error: {cb_error}")

            except Exception as e:
                logger.error(f"Error processing comment: {e}")

        @self._client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            logger.warning(f"Disconnected from @{self.username}")
            self._connected = False

    async def stop_listening(self) -> None:
        """Stop the TikTok listener"""
        if not self._running:
            return

        logger.info(f"Stopping TikTok listener for @{self.username}")
        self._running = False

        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

        if self._connect_task and not self._connect_task.done():
            self._connect_task.cancel()

        self._connected = False
        logger.info(f"TikTok listener stopped for @{self.username}")

    def is_connected(self) -> bool:
        """Check if listener is connected"""
        return self._running
