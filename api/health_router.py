"""
Health and Monitoring Router.

This module provides public, unauthenticated endpoints for health checks,
monitoring, and operational metrics. These endpoints are essential for ensuring
the reliability and observability of the Profile & Engagement API.

Endpoints Provided:
- `/healthcheck`: A basic, lightweight health check to confirm that the service
  is running.
- `/monitoring/ping`: A simple ping endpoint for basic connectivity testing.
- `/monitoring/detailed`: A comprehensive health check that verifies the status
  of all critical components, including the database and cache.
- `/monitoring/metrics`: Exposes detailed performance metrics, such as request
  counts, response times, and system resource usage.
- `/monitoring/cache/stats`: Provides statistics specific to the caching system.

Architectural Design:
- Public Access: All endpoints in this module are designed to be publicly
  accessible without authentication, making them suitable for use by automated
  health monitoring systems (e.g., Kubernetes probes, uptime checkers).
- Separation of Concerns: Health and monitoring endpoints are grouped into their
  own routers (`health_router` and `monitoring_router`) to keep them separate
  from the main application logic.
- Non-Blocking Operations: The endpoints are asynchronous and designed to be
  non-blocking, ensuring that health checks do not impact application performance.
- Graceful Degradation: The detailed health check is designed to report the
  status of individual components, allowing the system to report a "degraded"
  state rather than a complete failure if a non-critical component is down.
"""

from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

from core.logging_config import get_logger
from core.cache import get_cache
from core.performance import get_metrics_collector
from core.database import get_database_info

logger = get_logger(__name__)

# Create router without dependencies - no prefix to avoid conflicts
health_router = APIRouter(tags=["Health & Monitoring"])

# Separate monitoring router for additional endpoints
monitoring_router = APIRouter(prefix="/monitoring", tags=["Health & Monitoring"])


@health_router.get("/healthcheck")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint (no authentication required)

    Returns:
        Dict with status, timestamp, and version info
    """
    logger.debug("Health check requested")

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "Profile & Engagement API",
    }


@monitoring_router.get("/ping")
async def ping() -> Dict[str, str]:
    """Simple ping endpoint for connectivity testing"""
    logger.debug("Ping requested")
    return {
        "message": "pong",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@monitoring_router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with component status

    Note: This includes cache and metrics checks which may be slower
    """
    logger.info("Detailed health check requested")

    try:
        # Initialize with basic info
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "service": "Profile & Engagement API",
            "components": {},
        }

        # Check database
        try:
            db_info = await get_database_info()
            health_status["components"]["database"] = {
                "status": "healthy",
                "info": db_info,
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check cache (optional - only if enabled)
        try:
            cache = get_cache()
            cache_health = await cache.health_check()
            health_status["components"]["cache"] = cache_health

            if cache_health.get("status") != "healthy":
                health_status["status"] = "degraded"

        except Exception as e:
            logger.warning(f"Cache health check failed (non-critical): {e}")
            health_status["components"]["cache"] = {
                "status": "unavailable",
                "error": str(e),
            }

        # Check metrics collector (optional - only if enabled)
        try:
            metrics = get_metrics_collector()
            system_stats = metrics.get_stats(time_window_minutes=1)
            health_status["components"]["metrics"] = {
                "status": "healthy",
                "stats": {
                    "requests_last_minute": system_stats["requests"]["total"],
                    "avg_response_time_ms": system_stats["requests"]["avg_duration_ms"],
                    "system_cpu_percent": system_stats["system"]
                    .get("cpu", {})
                    .get("percent", 0),
                    "system_memory_percent": system_stats["system"]
                    .get("memory", {})
                    .get("percent", 0),
                },
            }
        except Exception as e:
            logger.warning(f"Metrics health check failed (non-critical): {e}")
            health_status["components"]["metrics"] = {
                "status": "unavailable",
                "error": str(e),
            }

        return health_status

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "service": "Profile & Engagement API",
            "error": str(e),
        }


@monitoring_router.get("/metrics")
async def get_metrics(time_window: int = 5) -> Dict[str, Any]:
    """Get performance metrics (no authentication required for monitoring)"""
    logger.info(f"Metrics requested with time_window={time_window}")

    try:
        metrics = get_metrics_collector()
        stats = metrics.get_stats(time_window_minutes=time_window)

        return {"metrics": stats, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {
            "error": "Metrics temporarily unavailable",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@monitoring_router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics (no authentication required for monitoring)"""
    logger.info("Cache stats requested")

    try:
        cache = get_cache()
        stats = await cache.stats()

        return {"cache_stats": stats, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Cache stats collection failed: {e}")
        return {
            "error": "Cache stats temporarily unavailable",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
