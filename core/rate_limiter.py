"""
Rate Limiting System.

This module implements a flexible rate limiting system for the Profile API, designed
to protect the service from abuse and ensure fair usage. It uses the token bucket
algorithm and supports different backends for both single-instance and distributed
environments.

Key Components:
- `RateLimitRule`: A dataclass that defines the parameters for a rate limit,
  including the number of requests, the time window, and the burst capacity.
- `TokenBucket`: An implementation of the token bucket algorithm, which provides
  a more flexible approach to rate limiting than a simple fixed window counter,
  allowing for short bursts of traffic.
- `MemoryRateLimiter`: An in-memory rate limiter suitable for single-instance
  deployments and development. It stores token buckets in a local dictionary.
- `RedisRateLimiter`: A placeholder for a Redis-based rate limiter that would be
  used in a distributed, multi-instance production environment to ensure
  globally consistent rate limiting. (Falls back to `MemoryRateLimiter`).
- `@rate_limit_decorator`: A decorator that provides a convenient way to apply
  rate limiting to specific API endpoints or functions.

Architectural Design:
- Strategy Pattern: The use of different rate limiter implementations
  (`MemoryRateLimiter`, `RedisRateLimiter`) that can be configured at startup is
  an example of the Strategy pattern. This allows the rate limiting strategy to
  be changed without altering the application code.
- Token Bucket Algorithm: The choice of the token bucket algorithm allows for a
  more sophisticated rate limiting strategy that can absorb temporary bursts of
  traffic, leading to a better user experience than a strict request-per-second
  limit.
- Centralized Configuration: Rate limiting rules are defined and managed in a
  central location (`get_rate_limiter`), making it easy to view and modify the
  rate limits for the entire application.
- Extensibility: The system is designed to be easily extensible. New rate limiting
  backends can be created by implementing a common interface, and new rules can
  be added as the application grows.
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading

from core.logging_config import get_logger
from core.exceptions import RateLimitError

logger = get_logger(__name__)


@dataclass
class RateLimitRule:
    """Rate limit rule configuration"""

    requests: int  # Number of requests allowed
    window: int  # Time window in seconds
    burst: Optional[int] = None  # Burst capacity (defaults to requests)

    def __post_init__(self):
        if self.burst is None:
            self.burst = self.requests


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""

    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float

    def __post_init__(self):
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket"""
        now = time.time()

        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Get time in seconds until tokens are available"""
        if self.tokens >= tokens:
            return 0.0

        needed_tokens = tokens - self.tokens
        return needed_tokens / self.refill_rate


class MemoryRateLimiter:
    """In-memory rate limiter using token bucket algorithm"""

    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.rules: Dict[str, RateLimitRule] = {}
        self._lock = threading.Lock()

    def add_rule(self, key: str, rule: RateLimitRule):
        """Add a rate limiting rule"""
        with self._lock:
            self.rules[key] = rule
            logger.info(
                f"Added rate limit rule for {key}: {rule.requests} requests per {rule.window}s"
            )

    def check_rate_limit(
        self, identifier: str, rule_key: str = "default"
    ) -> Tuple[bool, Dict[str, any]]:
        """Check if request is within rate limit"""
        with self._lock:
            if rule_key not in self.rules:
                # No rule defined, allow request
                return True, {"allowed": True, "remaining": float("inf")}

            rule = self.rules[rule_key]
            bucket_key = f"{rule_key}:{identifier}"

            # Get or create bucket
            if bucket_key not in self.buckets:
                self.buckets[bucket_key] = TokenBucket(
                    capacity=rule.burst,
                    tokens=rule.burst,
                    refill_rate=rule.requests / rule.window,
                    last_refill=time.time(),
                )

            bucket = self.buckets[bucket_key]

            # Try to consume a token
            allowed = bucket.consume(1)

            info = {
                "allowed": allowed,
                "remaining": int(bucket.tokens),
                "reset_time": datetime.now()
                + timedelta(seconds=bucket.time_until_available(1)),
                "retry_after": bucket.time_until_available(1) if not allowed else 0,
            }

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for {identifier} on rule {rule_key}"
                )

            return allowed, info

    def reset_limit(self, identifier: str, rule_key: str = "default"):
        """Reset rate limit for an identifier"""
        with self._lock:
            bucket_key = f"{rule_key}:{identifier}"
            if bucket_key in self.buckets:
                rule = self.rules.get(rule_key)
                if rule:
                    self.buckets[bucket_key].tokens = rule.burst
                    logger.info(f"Reset rate limit for {identifier} on rule {rule_key}")

    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics"""
        with self._lock:
            return {
                "total_buckets": len(self.buckets),
                "total_rules": len(self.rules),
                "rules": {
                    k: {"requests": v.requests, "window": v.window, "burst": v.burst}
                    for k, v in self.rules.items()
                },
            }


class RedisRateLimiter:
    """Redis-based distributed rate limiter (placeholder for future implementation)"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        logger.warning(
            "Redis rate limiter not implemented yet, falling back to memory limiter"
        )
        self._memory_limiter = MemoryRateLimiter()

    def add_rule(self, key: str, rule: RateLimitRule):
        return self._memory_limiter.add_rule(key, rule)

    def check_rate_limit(
        self, identifier: str, rule_key: str = "default"
    ) -> Tuple[bool, Dict[str, any]]:
        return self._memory_limiter.check_rate_limit(identifier, rule_key)

    def reset_limit(self, identifier: str, rule_key: str = "default"):
        return self._memory_limiter.reset_limit(identifier, rule_key)

    def get_stats(self) -> Dict[str, any]:
        return self._memory_limiter.get_stats()


# Global rate limiter instance
_rate_limiter: Optional[MemoryRateLimiter] = None


def get_rate_limiter() -> MemoryRateLimiter:
    """Get the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = MemoryRateLimiter()

        # Add default rules
        _rate_limiter.add_rule(
            "api", RateLimitRule(requests=100, window=60)
        )  # 100 req/min
        _rate_limiter.add_rule(
            "auth", RateLimitRule(requests=10, window=60)
        )  # 10 req/min for auth
        _rate_limiter.add_rule(
            "connect", RateLimitRule(requests=5, window=60)
        )  # 5 connections/min

    return _rate_limiter


def init_rate_limiter(backend: str = "memory", **kwargs) -> MemoryRateLimiter:
    """Initialize the global rate limiter"""
    global _rate_limiter

    if backend == "redis":
        _rate_limiter = RedisRateLimiter(**kwargs)
    else:
        _rate_limiter = MemoryRateLimiter()

    # Add default rules
    _rate_limiter.add_rule("api", RateLimitRule(requests=100, window=60))
    _rate_limiter.add_rule("auth", RateLimitRule(requests=10, window=60))
    _rate_limiter.add_rule("connect", RateLimitRule(requests=5, window=60))

    logger.info(f"Initialized {backend} rate limiter")
    return _rate_limiter


def rate_limit_decorator(rule_key: str = "api", identifier_func=None):
    """Decorator for rate limiting functions"""

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            limiter = get_rate_limiter()

            # Get identifier (default to 'global' if no function provided)
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                identifier = "global"

            allowed, info = limiter.check_rate_limit(identifier, rule_key)

            if not allowed:
                raise RateLimitError(
                    f"Rate limit exceeded. Try again in {info['retry_after']:.1f} seconds"
                )

            return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            limiter = get_rate_limiter()

            # Get identifier
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                identifier = "global"

            allowed, info = limiter.check_rate_limit(identifier, rule_key)

            if not allowed:
                raise RateLimitError(
                    f"Rate limit exceeded. Try again in {info['retry_after']:.1f} seconds"
                )

            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
