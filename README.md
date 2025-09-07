# Profile & Engagement API

> **Enterprise-grade microservice for TikTok user data and real-time comment streaming**

The Profile & Engagement API is a standalone FastAPI microservice that serves as the centralized provider of TikTok user data and real-time comment streaming for the Quizztok platform. Built with modern async/await architecture, dependency injection, and enterprise-grade security patterns, this service handles all TikTok Live integration while maintaining clean separation from the main game logic.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue?logo=postgresql)](https://www.postgresql.org/)

## ✨ Key Features

- **🔒 Dual Authentication** - API Key & JWT token authentication with comprehensive middleware
- **⚡ High-Performance Async Architecture** - Built on Python 3.11+ async/await with SQLAlchemy async support
- **🏛️ Clean Architecture** - Separation of concerns with dependency injection patterns
- **📊 Real-time WebSocket Streaming** - Live TikTok comment feeds with connection management
- **💾 Intelligent 4-Tier Avatar Caching** - Live → Scraper → Generator → Initials fallback strategy
- **📈 Comprehensive Observability** - Structured logging, performance metrics, and health monitoring
- **🐳 Docker Optimized** - Full containerization with health checks and volume management
- **🔧 Dependency Injection** - Clean service composition with FastAPI Depends system

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** or **Docker Desktop**
- **PostgreSQL 15+** (for production) or SQLite (for development)
- **4GB RAM** minimum for optimal performance

### Environment Variables Setup

Create a `.env` file in the `profile_api` directory:

```bash
# API Security
API_KEY="dev-api-key-12345"
JWT_SECRET_KEY="your-jwt-secret-key-for-development"

# Database Configuration (SQLite for development)
DATABASE_URL="sqlite+aiosqlite:///./profiles.db"

# Optional: PostgreSQL for production
# DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/profile_db"

# Logging and Monitoring
LOG_LEVEL="INFO"
```

### Option 1: Docker Compose (Recommended)

Get the full microservices stack running in under 2 minutes:

```bash
# Start Profile API with full Quizztok stack (from project root)
docker compose --profile dev up -d

# Or start Profile API standalone
docker compose --profile dev up profile_api -d

# Verify service is running
curl http://localhost:8002/healthcheck
```

**🎉 Service Available At:**
- **API Documentation**: http://localhost:8002/docs
- **Health Check**: http://localhost:8002/healthcheck
- **Admin Interface**: http://localhost:8002/auth/admin (with API key)
- **Monitoring**: http://localhost:8002/monitoring/detailed
- **Profile API Tester**: http://localhost:3001 (testing interface)

### Option 2: Docker Standalone

Run Profile API in isolated Docker container:

```bash
# Build and run Profile API only
cd profile_api/
docker build -t profile-api:dev .
docker run -d \
  --name profile-api-standalone \
  -p 8002:8002 \
  -e API_KEY="dev-api-key-12345" \
  -e DATABASE_URL="sqlite:///./profiles.db" \
  profile-api:dev
```

### Option 3: Manual Setup (Local Development)

For local development and testing:

```bash
# Navigate to profile_api directory
cd profile_api/

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use .env file)
export API_KEY="dev-api-key-12345"
export DATABASE_URL="sqlite+aiosqlite:///./profiles.db"
export LOG_LEVEL="DEBUG"

# Initialize the database and start the service
python main.py

# Alternatively, use uvicorn for development with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

The service will be available at: http://localhost:8002

**Development API Key**: Use `dev-api-key-12345` for testing and development

## 🔐 Authentication

The Profile API uses a **dual authentication system** supporting both API Keys and JWT tokens:

### 1. API Key Authentication (Primary Method)

API Key authentication is the recommended method for service-to-service communication. Include the API key in the `X-API-Key` header:

```bash
# Using curl with API key
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8002/status

# Using environment variable
export API_KEY="dev-api-key-12345"
curl -H "X-API-Key: $API_KEY" http://localhost:8002/status

# For WebSocket connections, include API key as query parameter
wscat -c "ws://localhost:8002/ws/comments/test-session?api_key=dev-api-key-12345"
```

**Development API Key**: Use `dev-api-key-12345` for testing and development environments.

### 2. JWT Token Authentication (Advanced)

JWT authentication is available for user-level access and administrative functions:

```bash
# Get JWT token by authenticating
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}'

# Use JWT token in Authorization header
curl -H "Authorization: Bearer your-jwt-token-here" http://localhost:8002/profile/username

# Refresh token (if configured)
curl -X POST http://localhost:8002/auth/refresh \
  -H "Authorization: Bearer your-refresh-token"
```

### Authentication Priority

1. **API Key** (X-API-Key header) - Highest priority
2. **JWT Token** (Authorization: Bearer header) - Secondary
3. **Public endpoints** (/healthcheck, /monitoring/ping) - No authentication required

## 📡 API Endpoints

### Core Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/healthcheck` | GET | Basic service health check | ❌ |
| `/monitoring/ping` | GET | Simple ping endpoint for connectivity testing | ❌ |
| `/monitoring/detailed` | GET | Comprehensive health check with component status | ❌ |
| `/monitoring/metrics` | GET | Performance metrics and system statistics | ❌ |
| `/status` | GET | Detailed service status and connection statistics | ✅ |
| `/profile/{username}` | GET | Get TikTok user profile with avatar data | ✅ |
| `/profiles/revalidate` | POST | Trigger background revalidation of user profiles | ✅ |
| `/connect` | POST | Start TikTok livestream capture session | ✅ |
| `/disconnect` | POST | Stop TikTok livestream capture session | ✅ |
| `/sessions` | GET | List active TikTok Live sessions | ✅ |
| `/sessions/cleanup` | POST | Clean up disconnected sessions | ✅ |

### Authentication Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/auth/register` | POST | Register new user account | ❌ |
| `/auth/login` | POST | Login and receive JWT token | ❌ |
| `/auth/refresh` | POST | Refresh JWT token | ✅ |
| `/auth/api-keys` | GET | List available API keys | ✅ |
| `/auth/api-keys/generate` | POST | Generate new API key | ✅ |
| `/auth/api-keys/revoke` | POST | Revoke existing API key | ✅ |

### WebSocket Endpoints

| Endpoint | Protocol | Description | Auth Required |
|----------|----------|-------------|---------------|
| `/ws/comments/{session_id}` | WebSocket | Real-time TikTok comment streaming | ✅ |

### Utility Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/cache/clear-expired` | POST | Clear expired profiles from cache | ✅ |
| `/cache/stats` | GET | Get cache statistics and metrics | ✅ |

## 🏗️ Service Architecture

The Profile API follows a **Clean Architecture** pattern with clear separation of concerns and dependency injection:

```
📁 Profile & Engagement API
├── 🔐 API Layer (Endpoints)      # FastAPI routers, request/response models
├── 🎯 Application Layer          # Use cases, service orchestration
├── 🏗️  Core Layer               # Domain models, exceptions, interfaces
├── 💾 Infrastructure Layer       # Database, caching, external integrations
└── 🔌 Integration Layer         # TikTok Live, WebSocket streaming
```

### Architecture Principles

- **Async/Await First**: All I/O operations use Python 3.11+ async/await
- **Dependency Injection**: Services injected via FastAPI's `Depends()` system
- **Separation of Concerns**: Clear boundaries between API, business logic, and infrastructure
- **Testability**: Mockable interfaces and dependency injection for easy testing

### Core Components

- **FastAPI Application**: Async web framework with automatic OpenAPI documentation
- **Async Database Layer**: SQLAlchemy async with PostgreSQL/SQLite support
- **Dependency Injection**: Clean service composition with `get_avatar_service()`, `get_connection_service()`
- **Profile Service**: TikTok user data with intelligent 4-tier avatar caching system
- **Connection Service**: TikTok Live comment stream management with WebSocket broadcasting
- **Cache Manager**: Multi-layer caching with TTL and LRU eviction policies
- **Performance Monitor**: Real-time metrics collection and system monitoring
- **Security Middleware**: API key validation, rate limiting, and request sanitization

### Dependency Injection Pattern

```python
# Services are injected into endpoints
@router.get("/profile/{username}")
async def get_profile(
    username: str, 
    avatar_svc: AvatarService = Depends(get_avatar_service)
):
    profile = await avatar_svc.get_user_profile(username)
    return profile
```

### Async Database Operations

```python
# All database operations are async
async with db_manager.get_connection() as conn:
    result = await conn.execute(text("SELECT COUNT(*) FROM userprofile"))
    count = result.scalar()
```

## 🔧 Configuration

### Essential Environment Variables

```bash
# API Security (Required)
API_KEY="your-production-api-key"  # Used for service authentication
JWT_SECRET_KEY="your-jwt-secret-key"  # For JWT token signing

# Database Configuration (Required)
DATABASE_URL="sqlite+aiosqlite:///./profiles.db"  # SQLite for development
# DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/profile_db"  # PostgreSQL for production

# Performance & Monitoring
LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
RATE_LIMIT_REQUESTS="100"  # Requests per window
RATE_LIMIT_WINDOW="60"  # Time window in seconds

# Cache Configuration
CACHE_MAX_SIZE="1000"  # Maximum cache entries
CACHE_TTL="300"  # Default TTL in seconds
CACHE_MAX_MEMORY_MB="100"  # Maximum memory usage for cache

# TikTok Integration (Optional)
TIKTOK_USERNAME="your_tiktok_username"  # For testing and development
TIKTOK_SESSION_ID="your_session_id"  # Persistent session for reliability
```

### Database Configuration Examples

**SQLite (Development):**
```bash
DATABASE_URL="sqlite+aiosqlite:///./profiles.db"
```

**PostgreSQL (Production):**
```bash
DATABASE_URL="postgresql+asyncpg://username:password@localhost:5432/profile_db"
```

**PostgreSQL with Connection Pooling:**
```bash
DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db?pool_size=20&max_overflow=30"
```

### Development vs Production Configuration

**Development Configuration:**
```bash
API_KEY="dev-api-key-12345"
DATABASE_URL="sqlite+aiosqlite:///./profiles.db"
LOG_LEVEL="DEBUG"
CACHE_MAX_SIZE="500"
```

**Production Configuration:**
```bash
API_KEY="$(openssl rand -hex 32)"  # Generate secure random key
DATABASE_URL="postgresql+asyncpg://user:password@prod-db:5432/profile_db"
LOG_LEVEL="INFO"
CACHE_MAX_SIZE="10000"
RATE_LIMIT_REQUESTS="500"
RATE_LIMIT_WINDOW="60"
```

### Async Database Connection Pool

The service uses SQLAlchemy's async connection pooling:

- **Pool Size**: 20 connections by default
- **Max Overflow**: 30 additional connections when needed
- **Connection Recycling**: Every 3600 seconds (1 hour)
- **Pre-ping**: Enabled to validate connections before use
- **Timeout**: 30 seconds for connection acquisition

## 📊 Monitoring & Health Checks

### Health Endpoints

```bash
# Basic health check (no auth)
curl http://localhost:8002/healthcheck

# Detailed health with component status (no auth)
curl http://localhost:8002/monitoring/detailed

# Complete service status (requires auth)
curl -H "X-API-Key: your-key" http://localhost:8002/status
```

### Performance Metrics

```bash
# System metrics over last 5 minutes
curl http://localhost:8002/monitoring/metrics?time_window=5

# Cache statistics
curl http://localhost:8002/monitoring/cache/stats
```

### Structured Logging

The service provides comprehensive structured logging with correlation IDs:

```json
{
  "timestamp": "2025-01-06T00:00:00.000Z",
  "level": "INFO",
  "message": "Request completed successfully",
  "correlation_id": "abc123",
  "duration_ms": 45,
  "endpoint": "/profile/username",
  "status_code": 200
}
```

## 🚀 Production Deployment

### Docker Production

```bash
# Build production image
docker build -t profile-api:latest .

# Run with production configuration
docker run -d \
  --name profile-api \
  -p 8002:8002 \
  -e API_KEY="your-production-key" \
  -e DATABASE_URL="postgresql://..." \
  -v profile_data:/app/data \
  profile-api:latest
```

### Docker Compose (Microservices)

**Complete Stack with Profile API Tester:**

```bash
# Start full development stack (includes Profile API Tester)
docker compose --profile dev up -d

# Check all services status
docker compose ps

# View Profile API logs
docker compose logs profile_api -f

# View Profile API Tester logs
docker compose logs profile_api_tester -f
```

**Available Services:**

| Service | Port | URL | Description |
|---------|------|-----|-------------|
| Profile API | 8002 | http://localhost:8002 | Main API service |
| Profile API Tester | 3001 | http://localhost:3001 | Testing interface |
| Game Backend | 8000 | http://localhost:8000 | Main game service |
| Frontend | 3000 | http://localhost:3000 | Quiz application |
| PostgreSQL | 5432 | localhost:5432 | Database |
| Redis | 6379 | localhost:6379 | Session storage |

**Docker Profiles Available:**

```bash
# Development (Profile API + dependencies)
docker compose --profile dev up -d

# Debug (includes Adminer + Dozzle logs)
docker compose --profile debug up -d

# Full stack (all services)
docker compose --profile full up -d
```

### Environment Setup

1. **Security**: Generate strong API keys and JWT secrets
2. **Database**: Configure PostgreSQL connection with pooling
3. **Monitoring**: Set up log aggregation and metrics collection
4. **Backup**: Configure database backup procedures
5. **Scaling**: Consider load balancing for high traffic

## 🧪 Testing

### Interactive Testing with Profile API Tester

**Web-based Testing Interface:**

```bash
# Start with Profile API Tester included
docker compose --profile dev up -d

# Access testing interface
open http://localhost:3001
```

The Profile API Tester provides:
- **Real-time WebSocket testing** - Connect to live comment streams
- **API endpoint testing** - Test all Profile API endpoints
- **Connection management** - Start/stop TikTok livestream connections
- **Comment visualization** - See live comments with timestamps
- **Error handling** - Visual feedback for connection issues

### Manual API Testing

```bash
# Test authentication
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}'

# Test profile endpoint
curl -H "X-API-Key: dev-api-key-12345" \
  http://localhost:8002/profile/tiktok_username

# Test WebSocket (requires WebSocket client)
wscat -c "ws://localhost:8002/ws/comments/test-session?api_key=dev-api-key-12345"
```

### Service Integration Testing

```bash
# Test Profile API to Game Backend communication
docker compose exec backend curl http://profile_api:8002/healthcheck

# Test Profile API Tester to Profile API communication
docker compose exec profile_api_tester curl http://profile_api:8002/healthcheck

# Test WebSocket connectivity between services
docker compose exec profile_api_tester node -e "
const ws = require('ws');
const client = new ws('ws://profile_api:8002/ws/comments/test?api_key=dev-api-key-12345');
client.on('open', () => { console.log('Connected!'); client.close(); });
client.on('error', err => console.error('Error:', err));
"
```

### Automated Testing

```bash
# Run Profile API test suite
docker compose exec profile_api pytest -v

# Run with coverage
docker compose exec profile_api pytest --cov=. --cov-report=html

# Local testing
cd profile_api/
pytest -v --cov=. --cov-report=html
```

## 🔍 Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check Docker Compose service logs
docker compose logs profile_api

# Check individual container logs
docker logs quizztok-profile-api

# Common solutions:
# 1. Verify API_KEY is set in docker-compose.yml
# 2. Check DATABASE_URL format
# 3. Ensure port 8002 is available
# 4. Wait for PostgreSQL health check to pass
```

**Profile API Tester connection issues:**
```bash
# Check Profile API Tester logs
docker compose logs profile_api_tester

# Verify Profile API is healthy
curl http://localhost:8002/healthcheck

# Test internal Docker network communication
docker compose exec profile_api_tester curl http://profile_api:8002/healthcheck

# Restart services in correct order
docker compose restart profile_api profile_api_tester
```

**Authentication errors:**
```bash
# Verify API key in Docker environment
docker compose exec profile_api env | grep API_KEY

# Test with development key
docker compose exec profile_api_tester curl -H "X-API-Key: dev-api-key-12345" http://profile_api:8002/status
```

**Database connection issues:**
```bash
# Check PostgreSQL health
docker compose exec postgres pg_isready -U quizztok_user -d quizztok_db

# Test database connection from Profile API
docker compose exec profile_api python -c "from core.database import test_connection; test_connection()"

# Switch to SQLite for development
docker compose exec profile_api env DATABASE_URL="sqlite:///./profiles.db"
```

**WebSocket connection failures:**
```bash
# Check WebSocket endpoint from Profile API Tester
docker compose exec profile_api_tester curl -I http://profile_api:8002/healthcheck

# Check network connectivity
docker compose exec profile_api_tester ping profile_api

# View WebSocket connection logs
docker compose logs profile_api | grep -i websocket
```

## 📚 Additional Documentation

- **[API Documentation](docs/API_DOCUMENTATION.md)** - Complete endpoint specifications with examples
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Security Guide](docs/SECURITY_GUIDE.md)** - Authentication and security best practices
- **[Operations Guide](docs/OPERATIONS_GUIDE.md)** - Monitoring and troubleshooting procedures
- **[Configuration Guide](docs/CONFIGURATION.md)** - All environment variables and settings

## ⚠️ Production Considerations

### Security
- **Never commit API keys** to version control
- **Use strong JWT secrets** (256-bit minimum)
- **Enable HTTPS** in production environments
- **Monitor authentication failures** and implement alerting

### Performance
- **Configure rate limiting** based on expected traffic
- **Monitor memory usage** and implement limits
- **Set up database connection pooling** for high concurrency
- **Implement proper caching strategies** for frequently accessed data

### Reliability
- **Set up health monitoring** with alerting
- **Implement database backup procedures**
- **Plan for disaster recovery scenarios**
- **Monitor external dependency health** (TikTok API)

## 🤝 Contributing

1. **Fork** the repository and create a feature branch
2. **Follow** the existing code patterns and security practices
3. **Add tests** for new functionality
4. **Update documentation** for any API changes
5. **Submit** a pull request with detailed description

## 📄 License

This project is part of the Quizztok platform and follows the same MIT License terms.

---

**🔗 Integration with Quizztok**

This Profile API is designed as a microservice for the [Quizztok platform](../README.md). It provides user profile data and real-time comment streams to the main game backend.

**📞 Support**

- **Issues**: Open a GitHub issue with detailed reproduction steps
- **Security**: Report security issues privately to the maintainers
- **Documentation**: Contribute improvements to help other developers

**⭐ If you find this service useful, please star the repository!**