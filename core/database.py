"""
Database Management and Configuration.

This module is responsible for setting up and managing the asynchronous database
connection for the Profile & Engagement API. It uses SQLAlchemy with `asyncio`
support and SQLModel for data modeling.

Key Components:
- `engine`: The core SQLAlchemy async engine, configured based on the
  `DATABASE_URL` environment variable. It supports both SQLite (for development)
  and PostgreSQL (for production).
- `async_session`: An asynchronous session factory that provides database
  sessions for interacting with the database.
- `create_db_and_tables`: A startup function that initializes the database and
  creates all necessary tables based on the SQLModel metadata.
- `get_session`: A dependency injection utility that provides a database session
  to API endpoints, ensuring that sessions are properly managed and closed.
- `get_database_info`: A health check function that provides diagnostic
  information about the database connection.

Architectural Design:
- Asynchronous Operations: The entire module is built around Python's `asyncio`,
  using `asyncpg` for PostgreSQL and `aiosqlite` for SQLite to ensure non-blocking
  database operations.
- Connection Pooling: The engine is configured with a connection pool
  (`AsyncAdaptedQueuePool`) to efficiently manage and reuse database connections,
  improving performance and scalability.
- Dependency Injection: The `get_session` function is designed to be used with
  FastAPI's dependency injection system, promoting clean code and easy testing.
- Environment-Driven Configuration: The database connection is configured via an
  environment variable, allowing the application to be easily deployed in
  different environments without code changes.
"""

import os
import logging
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import async_sessionmaker

# Get database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./profile_api.db")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create async engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration with aiosqlite
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,  # Set to True for SQL debugging
        poolclass=AsyncAdaptedQueuePool,
    )
else:
    # PostgreSQL configuration with asyncpg
    engine = create_async_engine(
        DATABASE_URL,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Validate connections before use
        echo=False,  # Set to True for SQL debugging
    )

# Create async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables():
    """
    Initialize the database and create all tables.
    Called during application startup.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logging.info("Profile API database tables created successfully")
    except Exception as e:
        logging.error(f"Failed to create Profile API database tables: {e}")
        raise


async def get_session():
    """
    Get an async database session for dependency injection.
    """
    async with async_session() as session:
        yield session


async def get_database_info():
    """
    Get basic database information for health checks.
    """
    try:
        # Test connection asynchronously
        async with async_session() as session:
            result = await session.execute("SELECT 1")
            await result.scalar()  # Ensure we actually get the result
            connection_healthy = True
    except Exception as e:
        logging.error(f"Database health check failed: {e}")
        connection_healthy = False

    return {
        "database_url": DATABASE_URL.split("@")[1]
        if "@" in DATABASE_URL
        else "masked",  # Hide credentials
        "connection_healthy": connection_healthy,
        "database_type": "postgresql" if "postgresql" in DATABASE_URL else "sqlite",
        "engine_info": {
            "pool_size": getattr(engine.pool, "size", lambda: "unknown")(),
            "checked_out": getattr(engine.pool, "checkedout", lambda: "unknown")(),
        },
    }


async def health_check():
    """
    Perform a comprehensive health check on the database.
    """
    try:
        async with async_session() as session:
            # Test basic connectivity
            result = await session.execute("SELECT 1")
            await result.scalar()

            # Test UserProfile table access
            result = await session.execute("SELECT COUNT(*) FROM userprofile")
            await result.scalar()

        return {
            "status": "healthy",
            "database_type": "postgresql" if "postgresql" in DATABASE_URL else "sqlite",
            "tables_accessible": True,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database_type": "postgresql" if "postgresql" in DATABASE_URL else "sqlite",
        }
