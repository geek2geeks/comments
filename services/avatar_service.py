"""
Avatar Service and Provider Orchestration.

This module defines the `AvatarService`, which is responsible for orchestrating the
retrieval of user profile information, with a primary focus on avatars. It manages
a chain of different avatar providers and handles caching to ensure high
performance and resilience.

Key Components:
- `AvatarService`: The central service class that orchestrates the process of
  fetching a user's profile. It manages a prioritized list of avatar providers
  and a caching layer.
- Provider Chain: The service uses a chain-of-responsibility pattern to try
  different avatar providers in order of priority (e.g., LiveAvatarProvider,
  ScraperAvatarProvider, GeneratorAvatarProvider). It returns the result from the
  first provider that succeeds.
- Caching Logic: The service includes logic for caching profiles in a database,
  checking if cached profiles are expired, and determining if a newly fetched
  profile is of higher quality than a cached one.
- Revalidation: It provides a mechanism to revalidate profiles in the background,
  ensuring that cached data remains fresh without impacting real-time requests.

Architectural Design:
- Strategy and Chain of Responsibility Patterns: The `AvatarService` uses a
  combination of these patterns. The different avatar providers are the
  "strategies," and the service tries them in a specific order, which is a form
  of the chain of responsibility pattern.
- Separation of Concerns: The `AvatarService` is responsible for the "what" and
  "when" of fetching an avatar (i.e., the orchestration and caching logic), while
  the individual `AvatarProvider` implementations are responsible for the "how"
  (i.e., the specific details of fetching from a particular source).
- Resilience: The provider fallback chain makes the service highly resilient.
  If one provider fails, the service automatically tries the next one, increasing
  the likelihood of successfully retrieving an avatar.
- Performance: The caching layer significantly improves performance by reducing
  the need for expensive network requests and scraping operations.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlmodel import select
from core.database import get_session
from core.models import UserProfile
from providers.avatar_provider import (
    AvatarProvider,
    LiveAvatarProvider,
    ScraperAvatarProvider,
    GeneratorAvatarProvider,
    InitialsAvatarProvider,
)

logger = logging.getLogger(__name__)


class AvatarService:
    """Service that orchestrates avatar providers and manages caching"""

    def __init__(self, providers: List[AvatarProvider] = None):
        """Initialize with list of providers in priority order"""
        if providers is None:
            # Default provider chain in priority order (highest to lowest)
            self.providers = [
                LiveAvatarProvider(),
                ScraperAvatarProvider(),
                GeneratorAvatarProvider(),
                InitialsAvatarProvider(),
            ]
        else:
            # Sort providers by priority (highest first)
            self.providers = sorted(providers, key=lambda p: p.priority, reverse=True)

    async def get_user_profile(
        self, username: str, nickname: str = None, live_avatar_url: str = None
    ) -> Optional[UserProfile]:
        """
        Get user profile with intelligent caching and provider fallback chain.

        Strategy:
        1. Check cache first
        2. If expired or not found, try providers in priority order
        3. Cache and return first successful result
        """
        try:
            # Step 1: Check cache first
            cached_profile = await self._get_cached_profile(username)
            if cached_profile and not self._is_expired(cached_profile):
                logger.info(
                    f"Cache hit for @{username} (source: {cached_profile.source})"
                )
                return cached_profile

            # Step 2: Try providers in priority order
            for provider in self.providers:
                try:
                    logger.debug(
                        f"Trying {provider.__class__.__name__} for @{username}"
                    )

                    # Pass live_avatar_url to LiveAvatarProvider, others ignore it
                    if isinstance(provider, LiveAvatarProvider) and live_avatar_url:
                        profile = await provider.get_avatar(
                            username, nickname, live_avatar_url=live_avatar_url
                        )
                    else:
                        profile = await provider.get_avatar(username, nickname)

                    if profile:
                        # Check if this is better than cached version
                        if cached_profile and not self._is_better_profile(
                            profile, cached_profile
                        ):
                            logger.info(
                                f"New profile not better than cached for @{username}"
                            )
                            return cached_profile

                        # Step 3: Cache the new profile
                        await self._cache_profile(profile)
                        logger.info(
                            f"Profile obtained from {provider.__class__.__name__} for @{username}"
                        )
                        return profile

                except Exception as e:
                    logger.error(
                        f"Error with {provider.__class__.__name__} for @{username}: {e}"
                    )
                    continue

            # Fallback to cached profile even if expired
            if cached_profile:
                logger.warning(f"Using expired cached profile for @{username}")
                return cached_profile

            logger.error(f"All providers failed for @{username}")
            return None

        except Exception as e:
            logger.error(f"Error getting profile for @{username}: {e}")
            return None

    async def _get_cached_profile(self, username: str) -> Optional[UserProfile]:
        """Get profile from database cache"""
        try:
            async with get_session() as session:
                statement = select(UserProfile).where(UserProfile.username == username)
                result = await session.exec(statement)
                return result.first()
        except Exception as e:
            logger.error(f"Error getting cached profile for @{username}: {e}")
            return None

    def _is_expired(self, profile: UserProfile) -> bool:
        """Check if profile is expired"""
        if not profile.expires_at:
            return True
        return datetime.now() > profile.expires_at

    def _is_better_profile(
        self, new_profile: UserProfile, current_profile: UserProfile
    ) -> bool:
        """Determine if new profile is better than current one"""
        # Priority comparison
        if new_profile.priority > current_profile.priority:
            return True
        elif new_profile.priority < current_profile.priority:
            return False

        # Same priority - check if content actually changed
        if new_profile.image_hash and current_profile.image_hash:
            if new_profile.image_hash != current_profile.image_hash:
                logger.info(
                    f"Profile updated for @{new_profile.username}: content changed"
                )
                return True

        return False

    async def _cache_profile(self, profile: UserProfile) -> None:
        """Save profile to database cache"""
        try:
            async with get_session() as session:
                # Check if profile exists
                existing = await session.exec(
                    select(UserProfile).where(UserProfile.username == profile.username)
                ).first()

                if existing:
                    # Update existing
                    for key, value in profile.dict(exclude={"username"}).items():
                        setattr(existing, key, value)
                    session.add(existing)
                else:
                    # Add new
                    session.add(profile)

                await session.commit()
                logger.debug(f"Cached profile for @{profile.username}")

        except Exception as e:
            logger.error(f"Error caching profile for @{profile.username}: {e}")

    async def revalidate_profiles(self, usernames: List[str]) -> Dict[str, bool]:
        """
        Revalidate profiles by bypassing cache and fetching fresh data.
        Returns dict of username -> success status.
        """
        results = {}

        for username in usernames:
            try:
                logger.info(f"Revalidating profile for @{username}")

                # Get current cached profile for comparison
                current_profile = await self._get_cached_profile(username)

                # Try providers (excluding live since we don't have live URLs in background)
                non_live_providers = [
                    p for p in self.providers if not isinstance(p, LiveAvatarProvider)
                ]

                for provider in non_live_providers:
                    try:
                        new_profile = await provider.get_avatar(
                            username,
                            current_profile.nickname if current_profile else None,
                        )

                        if new_profile:
                            # Only update if actually better or no existing profile
                            if not current_profile or self._is_better_profile(
                                new_profile, current_profile
                            ):
                                await self._cache_profile(new_profile)
                                logger.info(
                                    f"Revalidated profile for @{username} using {provider.__class__.__name__}"
                                )
                                results[username] = True
                                break
                            else:
                                logger.info(f"No update needed for @{username}")
                                results[username] = True
                                break

                    except Exception as e:
                        logger.error(
                            f"Error revalidating @{username} with {provider.__class__.__name__}: {e}"
                        )
                        continue

                if username not in results:
                    results[username] = False

            except Exception as e:
                logger.error(f"Error revalidating profile for @{username}: {e}")
                results[username] = False

        return results

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            async with get_session() as session:
                # Count profiles by source
                result = await session.exec(select(UserProfile))
                profiles = result.all()

                total = len(profiles)
                expired = sum(1 for p in profiles if self._is_expired(p))
                by_source = {}

                for profile in profiles:
                    source = profile.source or "unknown"
                    by_source[source] = by_source.get(source, 0) + 1

                return {
                    "total_profiles": total,
                    "valid_profiles": total - expired,
                    "expired_profiles": expired,
                    "by_source": by_source,
                    "providers_available": len(self.providers),
                }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}

    async def clear_expired_profiles(self) -> int:
        """Remove expired profiles from cache"""
        try:
            async with get_session() as session:
                now = datetime.now()
                result = await session.exec(
                    select(UserProfile).where(UserProfile.expires_at < now)
                )
                expired_profiles = result.all()

                count = len(expired_profiles)
                for profile in expired_profiles:
                    await session.delete(profile)

                await session.commit()
                logger.info(f"Cleared {count} expired profiles")
                return count

        except Exception as e:
            logger.error(f"Error clearing expired profiles: {e}")
            return 0
