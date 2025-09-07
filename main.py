"""
Profile & Engagement API - Main Application Entry Point.

This module initializes and configures the FastAPI application for the Profile &
Engagement API. It sets up logging, database connections, middleware, and routes.

The application serves as the primary interface for retrieving TikTok user profile
information and engaging with live comment streams. It is designed as a standalone
microservice, with the main game backend being its principal consumer.

Key Responsibilities:
- Configure and launch the FastAPI application.
- Set up middleware for correlation, error handling, performance, and security.
- Initialize core services like caching, rate limiting, and authentication.
- Mount API routers for different functionalities (health, auth, core API).
- Manage the application's lifecycle with startup and shutdown events.

Architecture:
The application follows a standard FastAPI structure, with a clear separation of
concerns between the main application file, routers, core services, and providers.
Middleware is used extensively to handle cross-cutting concerns, ensuring that
the application is robust, secure, and observable.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from core.database import create_db_and_tables
from api.endpoints import router, websocket_router
from api.auth_endpoints import router as auth_router
from api.health_router import health_router, monitoring_router
from core.logging_config import setup_logging, get_logger
from core.middleware import (
    PerformanceMiddleware,
    SecurityMiddleware,
    RequestValidationMiddleware,
)
from core.security_middleware import (
    RateLimitMiddleware,
    EnhancedAuthMiddleware,
    InputValidationMiddleware,
    SecurityHeadersMiddleware,
    SecurityAuditMiddleware,
)
from core.cache import init_cache, MemoryCacheBackend
from core.performance import init_metrics_collector
from core.rate_limiter import init_rate_limiter, RateLimitRule
from core.auth import init_auth_service, UserRole


# API Key security
async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    # Use generated API key from auth service if no environment variable set
    expected_key = os.getenv("API_KEY")
    if expected_key is None:
        # For development, allow bypassing with any key that starts with pk_
        if not x_api_key.startswith("pk_"):
            raise HTTPException(status_code=401, detail="Invalid API key format")
        return x_api_key
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger = get_logger("api.startup")
    try:
        await create_db_and_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Initialize cache system
    cache_backend = MemoryCacheBackend(max_size=2000, max_memory_mb=200)
    # cache_manager = init_cache(cache_backend)  # Currently unused
    init_cache(cache_backend)
    logger.info("Cache system initialized")

    # Initialize metrics collector
    metrics_collector = init_metrics_collector()
    logger.info("Performance monitoring initialized")

    # Initialize rate limiter
    rate_limiter = init_rate_limiter("memory")
    # Add custom rate limiting rules
    rate_limiter.add_rule("strict", RateLimitRule(requests=10, window=60))  # 10 req/min
    rate_limiter.add_rule(
        "websocket", RateLimitRule(requests=20, window=60)
    )  # 20 req/min
    logger.info("Rate limiter initialized")

    # Initialize authentication service
    auth_service = init_auth_service()
    # Create a default admin user for demo purposes
    try:
        admin_user = auth_service.register_user(
            username="admin",
            email="admin@example.com",
            password="Admin123!",
            role=UserRole.ADMIN,
        )
        # Generate default API key
        api_key, key_obj = auth_service.api_key_manager.generate_api_key(
            user_id=admin_user.id, name="Default Admin Key", permissions=["*"]
        )
        logger.info(f"Created default admin user with API key: {api_key}")
    except Exception as e:
        logger.info(f"Admin user already exists or creation failed: {e}")

    logger.info("Authentication service initialized")

    logger.info("Service startup completed - monitoring endpoints should be accessible")
    yield

    # Cleanup on shutdown
    logger.info("Shutting down Profile API")
    metrics_collector.cleanup()
    logger.info("Cleanup completed")


app = FastAPI(
    title="Profile & Engagement API",
    description="Standalone API for TikTok user data and live comments",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS middleware (required for frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3003",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Production middleware stack (all components working properly)
app.add_middleware(PerformanceMiddleware)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(EnhancedAuthMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SecurityAuditMiddleware)

# Initialize logger for endpoints
logger = get_logger("api.main")

# Health endpoints are now handled by dedicated health_router


# Include routers in priority order

# Health routers FIRST (no authentication required for monitoring)
app.include_router(health_router)
app.include_router(monitoring_router)

# Authentication router (no dependencies - handles its own auth)
app.include_router(auth_router)

# Include WebSocket router (no API key required for WebSocket)
app.include_router(websocket_router)

# Main API router (with API key verification for security) - LAST to avoid catching health endpoints
app.include_router(router, dependencies=[Depends(verify_api_key)])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,  # Back to production port
        reload=True,
        log_level="info",
    )
