"""
Avatar Provider Classes

Refactored avatar capture logic into clean provider classes with single responsibility.
Each provider implements a specific method of capturing avatars.
"""

import asyncio
import base64
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup
from core.models import UserProfile

logger = logging.getLogger(__name__)

# Avatar Priority System (Higher number = Higher priority)
AVATAR_PRIORITY = {
    "live": 10,  # Highest: Real TikTok Live photos
    "scraper": 9,  # High: Real profile photos
    "generator": 3,  # Low: Generated avatars
    "initials": 1,  # Lowest: Fallback initials
}


class AvatarProvider(ABC):
    """Abstract base class for all avatar providers"""

    @abstractmethod
    async def get_avatar(
        self, username: str, nickname: str = None, **kwargs
    ) -> Optional[UserProfile]:
        """Get avatar for a user. Returns UserProfile or None if failed."""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """Provider priority (higher = better quality)"""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier for this provider"""
        pass


class LiveAvatarProvider(AvatarProvider):
    """Capture avatars from live TikTok streams"""

    def __init__(self, cache_duration_hours: int = 168):  # 1 week for live avatars
        self.cache_duration_hours = cache_duration_hours

    @property
    def priority(self) -> int:
        return AVATAR_PRIORITY["live"]

    @property
    def source_name(self) -> str:
        return "live"

    async def get_avatar(
        self, username: str, nickname: str = None, live_avatar_url: str = None, **kwargs
    ) -> Optional[UserProfile]:
        """Capture avatar from live stream URL"""
        if not live_avatar_url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    live_avatar_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        avatar_bytes = await response.read()
                        avatar_base64 = base64.b64encode(avatar_bytes).decode("utf-8")
                        avatar_data_url = f"data:image/jpeg;base64,{avatar_base64}"

                        now = datetime.now()
                        image_hash = self._calculate_image_hash(avatar_bytes)

                        return UserProfile(
                            username=username,
                            nickname=nickname or username,
                            avatar_url=live_avatar_url,
                            avatar_data_url=avatar_data_url,
                            source=self.source_name,
                            priority=self.priority,
                            image_hash=image_hash,
                            last_checked_at=now,
                            expires_at=now + timedelta(hours=self.cache_duration_hours),
                        )
            return None

        except Exception as e:
            logger.error(f"Error capturing live avatar for {username}: {e}")
            return None

    def _calculate_image_hash(self, image_data: bytes) -> str:
        """Calculate SHA256 hash of image data for change detection"""
        return hashlib.sha256(image_data).hexdigest()


class ScraperAvatarProvider(AvatarProvider):
    """Scrape avatars from TikTok profile pages"""

    def __init__(self, cache_duration_hours: int = 24):
        self.cache_duration_hours = cache_duration_hours
        self.scraper_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    @property
    def priority(self) -> int:
        return AVATAR_PRIORITY["scraper"]

    @property
    def source_name(self) -> str:
        return "scraper"

    async def get_avatar(
        self, username: str, nickname: str = None, **kwargs
    ) -> Optional[UserProfile]:
        """Scrape avatar from TikTok profile with multiple User-Agent rotation"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

        for attempt, user_agent in enumerate(user_agents, 1):
            try:
                result = await self._scrape_with_user_agent(
                    username, nickname or username, user_agent
                )
                if result:
                    return result

                # Add delay between attempts
                if attempt < len(user_agents):
                    await asyncio.sleep(2 + attempt)

            except Exception as e:
                logger.debug(f"Scraping attempt {attempt} failed for @{username}: {e}")
                continue

        return None

    async def _scrape_with_user_agent(
        self, username: str, nickname: str, user_agent: str
    ) -> Optional[UserProfile]:
        """Scrape with custom User-Agent"""
        try:
            url = f"https://www.tiktok.com/@{username}"
            headers = {**self.scraper_headers, "User-Agent": user_agent}

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(
                timeout=timeout, headers=headers
            ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    response_text = await response.text()

            # Extract avatar URL using JSON and DOM methods
            avatar_url = self._extract_avatar_from_json(response_text, username)
            if not avatar_url:
                avatar_url = self._extract_avatar_from_dom(response_text, username)

            if not avatar_url:
                return None

            # Download the avatar
            return await self._download_avatar(username, nickname, avatar_url)

        except Exception as e:
            logger.error(f"Error scraping avatar for @{username}: {e}")
            return None

    def _extract_avatar_from_json(
        self, html_content: str, username: str
    ) -> Optional[str]:
        """Extract avatar URL from embedded JSON data"""
        try:
            patterns = [
                r'"avatarLarger":"(.*?)"',
                r'"avatarMedium":"(.*?)"',
                r'"avatarThumb":"(.*?)"',
            ]

            for pattern in patterns:
                match = re.search(pattern, html_content)
                if match:
                    avatar_url = match.group(1)
                    avatar_url = avatar_url.replace("\\u002F", "/").replace("\\/", "/")

                    if avatar_url.startswith("http") and (
                        "tiktok" in avatar_url or "bytedance" in avatar_url
                    ):
                        return avatar_url
            return None

        except Exception as e:
            logger.error(f"Error extracting avatar from JSON for @{username}: {e}")
            return None

    def _extract_avatar_from_dom(
        self, html_content: str, username: str
    ) -> Optional[str]:
        """Extract avatar URL from DOM using CSS selectors"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            avatar_selectors = [
                'img[data-e2e="user-avatar"]',
                "img.tiktok-avatar",
                'span[data-e2e="user-avatar"] img',
                'div[data-e2e="user-avatar"] img',
                ".avatar img",
                'img[alt*="avatar"]',
                'img[src*="avatar"]',
            ]

            for selector in avatar_selectors:
                avatar_img = soup.select_one(selector)
                if avatar_img and avatar_img.get("src"):
                    avatar_url = avatar_img["src"]
                    if avatar_url.startswith("http"):
                        return avatar_url
            return None

        except Exception as e:
            logger.error(f"Error extracting avatar from DOM for @{username}: {e}")
            return None

    async def _download_avatar(
        self, username: str, nickname: str, avatar_url: str
    ) -> Optional[UserProfile]:
        """Download avatar image and create UserProfile"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    avatar_url, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        avatar_bytes = await response.read()

                        # Validate size
                        if (
                            len(avatar_bytes) > 5 * 1024 * 1024
                            or len(avatar_bytes) < 100
                        ):
                            return None

                        # Create data URL
                        avatar_base64 = base64.b64encode(avatar_bytes).decode("utf-8")
                        content_type = response.headers.get(
                            "content-type", "image/jpeg"
                        )
                        avatar_data_url = f"data:{content_type};base64,{avatar_base64}"

                        now = datetime.now()
                        image_hash = hashlib.sha256(avatar_bytes).hexdigest()

                        return UserProfile(
                            username=username,
                            nickname=nickname,
                            avatar_url=avatar_url,
                            avatar_data_url=avatar_data_url,
                            source=self.source_name,
                            priority=self.priority,
                            image_hash=image_hash,
                            last_checked_at=now,
                            expires_at=now + timedelta(hours=self.cache_duration_hours),
                        )
            return None

        except Exception as e:
            logger.error(f"Error downloading avatar for @{username}: {e}")
            return None


class GeneratorAvatarProvider(AvatarProvider):
    """Generate avatars using free online services"""

    def __init__(self, cache_duration_days: int = 30):
        self.cache_duration_days = cache_duration_days

    @property
    def priority(self) -> int:
        return AVATAR_PRIORITY["generator"]

    @property
    def source_name(self) -> str:
        return "generator"

    async def get_avatar(
        self, username: str, nickname: str = None, **kwargs
    ) -> Optional[UserProfile]:
        """Generate avatar using free services"""
        avatar_services = [
            f"https://api.dicebear.com/7.x/adventurer/svg?seed={username}",
            f"https://api.dicebear.com/7.x/personas/svg?seed={username}",
            f"https://api.dicebear.com/7.x/identicon/svg?seed={username}",
            f"https://source.boringavatars.com/beam/120/{username}?colors=264653,2a9d8f,e9c46a,f4a261,e76f51",
        ]

        for service_url in avatar_services:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(service_url) as response:
                        if response.status == 200:
                            content = await response.read()
                            if len(content) > 100:
                                # Convert to data URL
                                if service_url.endswith(".svg"):
                                    data_url = f"data:image/svg+xml;base64,{base64.b64encode(content).decode()}"
                                else:
                                    content_type = response.headers.get(
                                        "content-type", "image/png"
                                    )
                                    data_url = f"data:{content_type};base64,{base64.b64encode(content).decode()}"

                                now = datetime.now()
                                return UserProfile(
                                    username=username,
                                    nickname=nickname or username,
                                    avatar_url=service_url,
                                    avatar_data_url=data_url,
                                    source=self.source_name,
                                    priority=self.priority,
                                    image_hash=hashlib.sha256(content).hexdigest(),
                                    last_checked_at=now,
                                    expires_at=now
                                    + timedelta(days=self.cache_duration_days),
                                )

            except Exception as e:
                logger.debug(f"Generator service failed for @{username}: {e}")
                continue

        return None


class InitialsAvatarProvider(AvatarProvider):
    """Generate simple initials-based avatars (always works)"""

    def __init__(self, cache_duration_days: int = 365):
        self.cache_duration_days = cache_duration_days

    @property
    def priority(self) -> int:
        return AVATAR_PRIORITY["initials"]

    @property
    def source_name(self) -> str:
        return "initials"

    async def get_avatar(
        self, username: str, nickname: str = None, **kwargs
    ) -> Optional[UserProfile]:
        """Create initials-based avatar (100% success rate)"""
        try:
            display_name = nickname or username

            # Extract initials
            initials = self._get_initials(display_name, username)

            # Generate consistent color
            username_hash = hashlib.md5(username.encode()).hexdigest()
            r = int(username_hash[0:2], 16)
            g = int(username_hash[2:4], 16)
            b = int(username_hash[4:6], 16)

            # Ensure good contrast
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            text_color = "#ffffff" if brightness < 128 else "#000000"
            bg_color = f"rgb({r},{g},{b})"

            # Create SVG
            svg_content = f'''<svg width="120" height="120" xmlns="http://www.w3.org/2000/svg">
                <circle cx="60" cy="60" r="60" fill="{bg_color}"/>
                <text x="60" y="75" font-family="Arial, sans-serif" font-size="40" font-weight="bold" 
                      text-anchor="middle" fill="{text_color}">{initials}</text>
            </svg>'''

            data_url = f"data:image/svg+xml;base64,{base64.b64encode(svg_content.encode()).decode()}"

            now = datetime.now()
            return UserProfile(
                username=username,
                nickname=display_name,
                avatar_url=f"initials://{initials}",
                avatar_data_url=data_url,
                source=self.source_name,
                priority=self.priority,
                image_hash=hashlib.sha256(svg_content.encode()).hexdigest(),
                last_checked_at=now,
                expires_at=now + timedelta(days=self.cache_duration_days),
            )

        except Exception as e:
            logger.error(f"Failed to create initials avatar for @{username}: {e}")
            return None

    def _get_initials(self, display_name: str, username: str) -> str:
        """Extract initials from display name and username"""
        initials = ""
        if display_name:
            initials += display_name[0].upper()
            if len(display_name.split()) > 1:
                initials += display_name.split()[1][0].upper()
            elif len(display_name) > 1:
                initials += display_name[1].upper()

        if len(initials) < 2:
            initials = (
                username[0] + username[1] if len(username) > 1 else username[0] + "U"
            ).upper()

        return initials
