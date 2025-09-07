# Profile API Configuration Guide

> **Complete configuration reference for the Profile & Engagement API**

This guide provides comprehensive information about all configuration options, environment variables, and settings for the Profile API. It covers development, staging, and production configurations with security best practices.

## 📋 Configuration Overview

The Profile API uses environment variables for configuration, allowing flexible deployment across different environments without code changes. Configuration is organized into several categories:

- **Core Settings** - Essential service configuration
- **Security Settings** - Authentication, rate limiting, and security headers
- **Database Settings** - Database connection and optimization
- **Cache Settings** - Cache configuration and performance
- **Logging Settings** - Log levels, formats, and destinations
- **Performance Settings** - Concurrency, timeouts, and optimization
- **Monitoring Settings** - Health checks and metrics collection

## 🔧 Core Configuration

### Required Environment Variables

These variables must be set for the service to function properly:

#### API_KEY
**Purpose**: Primary authentication key for API access  
**Format**: String (recommended: `pk_` prefix + 32+ characters)  
**Required**: Yes  
**Security**: High - Store securely, never commit to version control

```bash
# Development (environment-based authentication)
export API_KEY="dev-api-key-12345"

# Production (generate secure key with pk_ prefix)
export API_KEY="pk_$(openssl rand -hex 32)"

# Docker development
-e API_KEY="dev-api-key-12345"

# Docker production
-e API_KEY="pk_your-secure-production-key"
```

**Development Authentication Behavior:**
- Keys **without** `pk_` prefix are validated against the `API_KEY` environment variable
- Matching environment keys automatically create a development user with SERVICE role
- Development keys receive wildcard `["*"]` permissions for full API access
- Development users persist for the service lifetime
- **Important**: Environment-based authentication is for development only

#### DATABASE_URL
**Purpose**: Database connection string  
**Format**: SQLite or PostgreSQL connection URL  
**Required**: Yes  
**Default**: `sqlite:///./profiles.db`

```bash
# SQLite (Development)
export DATABASE_URL="sqlite:///./profiles.db"

# PostgreSQL (Production)
export DATABASE_URL="postgresql://user:password@localhost:5432/quizztok_db"

# PostgreSQL with async driver
export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/quizztok_db"
```

### Optional Core Settings

#### HOST
**Purpose**: Server bind address  
**Default**: `0.0.0.0`  
**Options**: IP address or hostname

```bash
# Bind to all interfaces (default)
export HOST="0.0.0.0"

# Bind to localhost only
export HOST="127.0.0.1"

# Bind to specific interface
export HOST="192.168.1.100"
```

#### PORT
**Purpose**: Server port number  
**Default**: `8002`  
**Range**: 1024-65535 (recommended: 8000-9000)

```bash
# Default port
export PORT="8002"

# Alternative port
export PORT="8080"

# Production port behind reverse proxy
export PORT="8000"
```

#### LOG_LEVEL
**Purpose**: Logging verbosity  
**Default**: `INFO`  
**Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

```bash
# Development - verbose logging
export LOG_LEVEL="DEBUG"

# Production - standard logging
export LOG_LEVEL="INFO"

# Production - minimal logging
export LOG_LEVEL="WARNING"
```

## 🔐 Security Configuration

### Authentication Settings

#### JWT_SECRET_KEY
**Purpose**: JWT token signing key  
**Format**: Base64 encoded string (256-bit recommended)  
**Required**: Auto-generated if not provided  
**Security**: Critical - Must be kept secret

```bash
# Generate secure key
export JWT_SECRET_KEY="$(openssl rand -base64 32)"

# Set explicit key
export JWT_SECRET_KEY="your-256-bit-secret-key-here"
```

#### JWT_ACCESS_TOKEN_EXPIRE
**Purpose**: Access token lifetime in seconds  
**Default**: `3600` (1 hour)  
**Range**: 300-86400 (5 minutes to 24 hours)

```bash
# Default (1 hour)
export JWT_ACCESS_TOKEN_EXPIRE="3600"

# Short-lived tokens (15 minutes)
export JWT_ACCESS_TOKEN_EXPIRE="900"

# Long-lived tokens (8 hours)
export JWT_ACCESS_TOKEN_EXPIRE="28800"
```

#### JWT_REFRESH_TOKEN_EXPIRE
**Purpose**: Refresh token lifetime in seconds  
**Default**: `604800` (7 days)  
**Range**: 3600-2592000 (1 hour to 30 days)

```bash
# Default (7 days)
export JWT_REFRESH_TOKEN_EXPIRE="604800"

# Short-lived (1 day)
export JWT_REFRESH_TOKEN_EXPIRE="86400"

# Long-lived (30 days)
export JWT_REFRESH_TOKEN_EXPIRE="2592000"
```

### Rate Limiting Configuration

#### API Rate Limits
**Purpose**: Control request rates for different endpoint categories

```bash
# General API endpoints
export RATE_LIMIT_API_REQUESTS="100"     # requests
export RATE_LIMIT_API_WINDOW="60"        # window in seconds

# Authentication endpoints (stricter)
export RATE_LIMIT_AUTH_REQUESTS="10"
export RATE_LIMIT_AUTH_WINDOW="60"

# Connection endpoints (very strict)
export RATE_LIMIT_CONNECT_REQUESTS="5"
export RATE_LIMIT_CONNECT_WINDOW="300"   # 5 minutes

# WebSocket connections
export RATE_LIMIT_WEBSOCKET_REQUESTS="20"
export RATE_LIMIT_WEBSOCKET_WINDOW="60"
```

#### Rate Limit Backend
**Purpose**: Storage backend for rate limiting data  
**Default**: `memory`  
**Options**: `memory`, `redis`

```bash
# In-memory (development)
export RATE_LIMIT_BACKEND="memory"

# Redis (production)
export RATE_LIMIT_BACKEND="redis"
export REDIS_URL="redis://localhost:6379/0"
```

### Security Headers Configuration

#### Security Headers Control
**Purpose**: Enable/disable security headers

```bash
# Enable all security headers (recommended)
export SECURITY_HEADERS_ENABLED="true"

# HTTP Strict Transport Security
export SECURITY_HEADERS_HSTS="true"
export HSTS_MAX_AGE="31536000"                    # 1 year
export HSTS_INCLUDE_SUBDOMAINS="true"

# Content Security Policy
export SECURITY_HEADERS_CSP="true"
export CSP_DEFAULT_SRC="'self'"
export CSP_SCRIPT_SRC="'self'"
export CSP_STYLE_SRC="'self' 'unsafe-inline'"
export CSP_IMG_SRC="'self' data: https:"

# Frame Options
export SECURITY_HEADERS_FRAME_OPTIONS="DENY"      # DENY, SAMEORIGIN

# Content Type Options
export SECURITY_HEADERS_NOSNIFF="true"

# XSS Protection
export SECURITY_HEADERS_XSS_PROTECTION="1; mode=block"

# Referrer Policy
export REFERRER_POLICY="strict-origin-when-cross-origin"
```

## 🗄️ Database Configuration

### Connection Settings

#### Connection Pool Configuration
**Purpose**: Optimize database connection management

```bash
# SQLite settings
export SQLITE_TIMEOUT="30"                        # seconds
export SQLITE_WAL_ENABLED="true"                  # Write-Ahead Logging

# PostgreSQL settings
export DB_POOL_SIZE="10"                          # connection pool size
export DB_MAX_OVERFLOW="20"                       # additional connections
export DB_POOL_TIMEOUT="30"                       # connection timeout
export DB_POOL_RECYCLE="3600"                     # connection lifetime
```

#### Database Optimization

```bash
# SQLite optimization
export SQLITE_JOURNAL_MODE="WAL"                  # WAL, DELETE, TRUNCATE
export SQLITE_SYNCHRONOUS="NORMAL"                # FULL, NORMAL, OFF
export SQLITE_CACHE_SIZE="2000"                   # pages in cache

# PostgreSQL optimization
export DB_STATEMENT_TIMEOUT="30000"               # 30 seconds
export DB_LOCK_TIMEOUT="10000"                    # 10 seconds
export DB_IDLE_IN_TRANSACTION_TIMEOUT="60000"     # 1 minute
```

### Backup Configuration

```bash
# Backup settings
export BACKUP_ENABLED="true"
export BACKUP_INTERVAL="3600"                     # 1 hour
export BACKUP_RETENTION_DAYS="30"
export BACKUP_DIRECTORY="/app/backups"

# Remote backup (optional)
export BACKUP_S3_ENABLED="false"
export BACKUP_S3_BUCKET="your-backup-bucket"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

## ⚡ Cache Configuration

### Cache Backend Settings

#### Memory Cache (Default)
**Purpose**: In-memory caching for development and small deployments

```bash
# Cache configuration
export CACHE_BACKEND="memory"
export CACHE_MAX_SIZE="2000"                      # maximum items
export CACHE_MAX_MEMORY_MB="200"                  # memory limit
export CACHE_DEFAULT_TTL="300"                    # 5 minutes default TTL
export CACHE_CLEANUP_INTERVAL="60"                # cleanup every minute
```

#### Redis Cache (Production)
**Purpose**: Redis-based caching for production deployments

```bash
# Redis cache configuration
export CACHE_BACKEND="redis"
export REDIS_URL="redis://localhost:6379/1"
export REDIS_PASSWORD="your-redis-password"
export REDIS_DB="1"                               # database number
export REDIS_MAX_CONNECTIONS="10"
export REDIS_RETRY_ON_TIMEOUT="true"
export REDIS_HEALTH_CHECK_INTERVAL="30"
```

### Cache Behavior Settings

```bash
# Cache TTL settings (seconds)
export CACHE_PROFILE_TTL="1800"                   # 30 minutes for profiles
export CACHE_SESSION_TTL="3600"                   # 1 hour for sessions
export CACHE_METRICS_TTL="60"                     # 1 minute for metrics

# Cache policies
export CACHE_EVICTION_POLICY="lru"                # lru, lfu, fifo
export CACHE_COMPRESSION="true"                   # compress cached values
export CACHE_SERIALIZER="pickle"                  # pickle, json, msgpack
```

### Cache API Implementation Notes

**Important**: The Profile API uses a simplified cache interface:
- `cache.get(key)` - Retrieve value by key only (no namespace parameter)
- `cache.set(key, value, ttl=None)` - Store value with optional TTL
- Keys should include any necessary namespacing in the key string itself

**Correct Usage Examples:**
```python
# Correct - single key parameter
cache_key = f"connection_attempt:{session_id}:{username}"
value = await cache.get(cache_key)
await cache.set(cache_key, data, ttl=300)

# Incorrect - multiple parameters (will cause TypeError)
await cache.get("connections", cache_key)  # ❌ Wrong
await cache.set("connections", cache_key, data, ttl=300)  # ❌ Wrong
```

**Connection Attempt Caching:**
The `/connect` endpoint uses connection attempt caching to prevent rapid retries:
- **Cache Key Format**: `connection_attempt:{session_id}:{username}`
- **Success Cache TTL**: 300 seconds (5 minutes)
- **Failure Cache TTL**: 300 seconds (5 minutes)
- **Purpose**: Rate limiting and connection state tracking

## 📊 Logging Configuration

### Basic Logging Settings

#### Log Level and Format
```bash
# Log levels by component
export LOG_LEVEL="INFO"                           # global log level
export LOG_LEVEL_DB="WARNING"                     # database logs
export LOG_LEVEL_CACHE="INFO"                     # cache logs
export LOG_LEVEL_AUTH="INFO"                      # authentication logs
export LOG_LEVEL_SECURITY="WARNING"               # security logs

# Log format
export LOG_FORMAT="json"                          # json, text
export LOG_STRUCTURED="true"                      # structured logging
export LOG_INCLUDE_TIMESTAMP="true"
export LOG_INCLUDE_CORRELATION_ID="true"
```

#### Log Destinations

```bash
# File logging
export LOG_TO_FILE="true"
export LOG_FILE_PATH="/var/log/profile-api/app.log"
export LOG_FILE_MAX_SIZE="100MB"                  # rotate at size
export LOG_FILE_BACKUP_COUNT="5"                  # keep 5 backups
export LOG_FILE_ROTATION="daily"                  # daily, weekly, monthly

# Console logging
export LOG_TO_CONSOLE="true"
export LOG_CONSOLE_LEVEL="INFO"
export LOG_CONSOLE_FORMAT="text"                  # text, json

# Remote logging (optional)
export LOG_REMOTE_ENABLED="false"
export LOG_REMOTE_ENDPOINT="https://logs.example.com/api/v1/logs"
export LOG_REMOTE_API_KEY="your-logging-api-key"
```

### Advanced Logging Settings

```bash
# Correlation ID tracking
export CORRELATION_ID_ENABLED="true"
export CORRELATION_ID_HEADER="X-Correlation-ID"
export CORRELATION_ID_LENGTH="12"

# Request logging
export LOG_REQUESTS="true"
export LOG_REQUEST_BODY="false"                   # security consideration
export LOG_RESPONSE_BODY="false"                  # security consideration
export LOG_SLOW_REQUESTS="true"
export LOG_SLOW_REQUEST_THRESHOLD="1000"          # milliseconds

# Security audit logging
export AUDIT_LOG_ENABLED="true"
export AUDIT_LOG_AUTHENTICATION="true"
export AUDIT_LOG_AUTHORIZATION="true"
export AUDIT_LOG_RATE_LIMITS="true"
export AUDIT_LOG_SUSPICIOUS_ACTIVITY="true"
```

## ⚡ Performance Configuration

### Application Performance

#### Concurrency Settings
```bash
# Server concurrency
export WEB_CONCURRENCY="4"                        # worker processes
export WORKER_CLASS="uvicorn.workers.UvicornWorker"
export MAX_WORKERS="10"                           # auto-scaling limit

# Request handling
export KEEP_ALIVE="2"                             # seconds
export MAX_REQUESTS="1000"                        # requests per worker
export MAX_REQUESTS_JITTER="50"                   # randomization
export PRELOAD_APP="true"                         # preload for faster startup
```

#### Timeout Settings
```bash
# Request timeouts
export REQUEST_TIMEOUT="30"                       # request timeout (seconds)
export KEEPALIVE_TIMEOUT="5"                      # keep-alive timeout
export CLIENT_TIMEOUT="60"                        # client connection timeout
export GRACEFUL_TIMEOUT="30"                      # graceful shutdown timeout

# Database timeouts
export DB_QUERY_TIMEOUT="30"                      # query timeout
export DB_CONNECTION_TIMEOUT="10"                 # connection timeout
export DB_POOL_TIMEOUT="30"                       # pool acquisition timeout

# Cache timeouts
export CACHE_OPERATION_TIMEOUT="5"                # cache operation timeout
export CACHE_CONNECTION_TIMEOUT="3"               # cache connection timeout
```

### Resource Limits

```bash
# Memory limits
export MEMORY_LIMIT_MB="1024"                     # 1GB memory limit
export MEMORY_WARNING_THRESHOLD="80"              # warning at 80%
export MEMORY_CRITICAL_THRESHOLD="90"             # critical at 90%

# CPU limits
export CPU_LIMIT_CORES="2"                        # CPU core limit
export CPU_WARNING_THRESHOLD="70"                 # warning at 70%
export CPU_CRITICAL_THRESHOLD="85"                # critical at 85%

# File descriptor limits
export MAX_FILE_DESCRIPTORS="4096"
export MAX_OPEN_FILES="2048"

# Request size limits
export MAX_REQUEST_SIZE="10485760"                # 10MB
export MAX_JSON_PAYLOAD="1048576"                 # 1MB
export MAX_FORM_FIELDS="1000"
```

## 📈 Monitoring Configuration

### Metrics Collection

#### Metrics Settings
```bash
# Metrics collection
export METRICS_ENABLED="true"
export METRICS_COLLECTION_INTERVAL="30"           # seconds
export METRICS_RETENTION_HOURS="24"               # keep 24 hours
export METRICS_MAX_DATAPOINTS="10000"

# System metrics
export COLLECT_SYSTEM_METRICS="true"
export COLLECT_CPU_METRICS="true"
export COLLECT_MEMORY_METRICS="true"
export COLLECT_DISK_METRICS="true"
export COLLECT_NETWORK_METRICS="true"

# Application metrics
export COLLECT_REQUEST_METRICS="true"
export COLLECT_DATABASE_METRICS="true"
export COLLECT_CACHE_METRICS="true"
export COLLECT_AUTH_METRICS="true"
```

#### Health Check Settings
```bash
# Health check configuration
export HEALTH_CHECK_ENABLED="true"
export HEALTH_CHECK_PATH="/healthcheck"
export HEALTH_CHECK_TIMEOUT="5"                   # seconds
export HEALTH_CHECK_INTERVAL="30"                 # for external monitors

# Component health checks
export HEALTH_CHECK_DATABASE="true"
export HEALTH_CHECK_CACHE="true"
export HEALTH_CHECK_EXTERNAL_SERVICES="false"

# Detailed health endpoint
export DETAILED_HEALTH_ENABLED="true"
export DETAILED_HEALTH_PATH="/monitoring/detailed"
export DETAILED_HEALTH_COMPONENTS="true"
```

### Alerting Configuration

```bash
# Alert settings
export ALERTING_ENABLED="false"                   # enable built-in alerting
export ALERT_EMAIL_ENABLED="false"
export ALERT_EMAIL_SMTP_HOST="smtp.example.com"
export ALERT_EMAIL_SMTP_PORT="587"
export ALERT_EMAIL_USERNAME="alerts@example.com"
export ALERT_EMAIL_PASSWORD="your-email-password"
export ALERT_EMAIL_TO="admin@example.com"

# Alert thresholds
export ALERT_RESPONSE_TIME_MS="1000"              # alert if response > 1s
export ALERT_ERROR_RATE_PERCENT="5"               # alert if error rate > 5%
export ALERT_MEMORY_USAGE_PERCENT="80"            # alert if memory > 80%
export ALERT_DISK_USAGE_PERCENT="85"              # alert if disk > 85%
```

## 🚀 Environment-Specific Configurations

### Development Environment

Create a `.env.development` file:

```bash
# Development Configuration
API_KEY="dev-api-key-12345"
DATABASE_URL="sqlite:///./profiles.db"
LOG_LEVEL="DEBUG"
LOG_TO_CONSOLE="true"
LOG_FORMAT="text"
CACHE_BACKEND="memory"
CACHE_MAX_SIZE="1000"
RATE_LIMIT_API_REQUESTS="1000"
METRICS_ENABLED="true"
SECURITY_HEADERS_ENABLED="false"
CORS_ALLOW_ORIGINS="*"
RELOAD="true"
```

### Staging Environment

Create a `.env.staging` file:

```bash
# Staging Configuration
API_KEY="staging-api-key-secure-random-string"
DATABASE_URL="postgresql://staging_user:staging_pass@db-staging:5432/quizztok_staging"
LOG_LEVEL="INFO"
LOG_TO_FILE="true"
LOG_FILE_PATH="/var/log/profile-api/staging.log"
CACHE_BACKEND="redis"
REDIS_URL="redis://redis-staging:6379/0"
RATE_LIMIT_API_REQUESTS="200"
METRICS_ENABLED="true"
SECURITY_HEADERS_ENABLED="true"
CORS_ALLOW_ORIGINS="https://staging.example.com"
RELOAD="false"
```

### Production Environment

Create a `.env.production` file:

```bash
# Production Configuration
API_KEY="${PROFILE_API_KEY}"                      # from secret manager
DATABASE_URL="${DATABASE_URL}"                    # from secret manager
JWT_SECRET_KEY="${JWT_SECRET_KEY}"                # from secret manager

# Server settings
HOST="0.0.0.0"
PORT="8002"
LOG_LEVEL="INFO"
RELOAD="false"
WEB_CONCURRENCY="4"

# Database settings
DB_POOL_SIZE="20"
DB_MAX_OVERFLOW="30"
DB_POOL_TIMEOUT="30"

# Cache settings
CACHE_BACKEND="redis"
REDIS_URL="${REDIS_URL}"                          # from secret manager
CACHE_MAX_SIZE="10000"
CACHE_MAX_MEMORY_MB="500"

# Security settings
SECURITY_HEADERS_ENABLED="true"
RATE_LIMIT_API_REQUESTS="100"
RATE_LIMIT_AUTH_REQUESTS="10"

# Logging settings
LOG_TO_FILE="true"
LOG_FILE_PATH="/var/log/profile-api/production.log"
LOG_STRUCTURED="true"
LOG_FORMAT="json"
AUDIT_LOG_ENABLED="true"

# Monitoring settings
METRICS_ENABLED="true"
HEALTH_CHECK_ENABLED="true"
ALERTING_ENABLED="true"

# Performance settings
REQUEST_TIMEOUT="30"
MAX_REQUEST_SIZE="10485760"
MEMORY_LIMIT_MB="2048"
CPU_LIMIT_CORES="4"
```

## 🐳 Docker Configuration

### Docker Environment Variables

```dockerfile
# Dockerfile environment setup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Runtime configuration via docker-compose.yml
services:
  profile_api:
    environment:
      - API_KEY=${PROFILE_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - CACHE_BACKEND=redis
      - REDIS_URL=redis://redis:6379/0
```

### Docker Compose Configuration

```yaml
version: '3.8'
services:
  profile_api:
    build: .
    environment:
      API_KEY: "${PROFILE_API_KEY}"
      DATABASE_URL: "${DATABASE_URL}"
      LOG_LEVEL: "${LOG_LEVEL:-INFO}"
      CACHE_BACKEND: "redis"
      REDIS_URL: "redis://redis:6379/0"
      RATE_LIMIT_BACKEND: "redis"
      METRICS_ENABLED: "true"
      SECURITY_HEADERS_ENABLED: "true"
    depends_on:
      - postgres
      - redis
    ports:
      - "8002:8002"
    volumes:
      - ./data:/app/data
      - ./logs:/var/log/profile-api
```

## ☸️ Kubernetes Configuration

### ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: profile-api-config
data:
  HOST: "0.0.0.0"
  PORT: "8002"
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
  CACHE_BACKEND: "redis"
  METRICS_ENABLED: "true"
  SECURITY_HEADERS_ENABLED: "true"
  RATE_LIMIT_API_REQUESTS: "100"
  HEALTH_CHECK_ENABLED: "true"
```

### Secret Example

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: profile-api-secrets
type: Opaque
data:
  API_KEY: <base64-encoded-api-key>
  DATABASE_URL: <base64-encoded-database-url>
  JWT_SECRET_KEY: <base64-encoded-jwt-secret>
  REDIS_URL: <base64-encoded-redis-url>
```

### Deployment Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: profile-api
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: profile-api-secrets
              key: API_KEY
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: profile-api-secrets
              key: DATABASE_URL
        envFrom:
        - configMapRef:
            name: profile-api-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
```

## 🔧 Configuration Management

### Environment Loading Priority

The Profile API loads configuration in the following order (later values override earlier ones):

1. **Default values** (hardcoded in application)
2. **Environment variables** (from system)
3. **.env file** (if present in working directory)
4. **Docker environment** (if running in container)
5. **Kubernetes ConfigMap/Secret** (if running in K8s)
6. **Command-line arguments** (if supported)

### Configuration Validation

The application validates configuration on startup:

```bash
# Test configuration
python -c "
import os
from core.config import validate_config
validate_config()
print('Configuration is valid')
"

# Check required variables
python -c "
import os
required = ['API_KEY', 'DATABASE_URL']
missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'Missing required variables: {missing}')
else:
    print('All required variables are set')
"
```

### Configuration Templates

#### Minimal Configuration (.env.minimal)
```bash
API_KEY="your-api-key-here"
DATABASE_URL="sqlite:///./profiles.db"
```

#### Complete Development Configuration (.env.development)
```bash
# Core settings
API_KEY="dev-api-key-12345"
DATABASE_URL="sqlite:///./profiles.db"
HOST="127.0.0.1"
PORT="8002"
LOG_LEVEL="DEBUG"

# Development features
RELOAD="true"
LOG_TO_CONSOLE="true"
LOG_FORMAT="text"
CACHE_BACKEND="memory"
RATE_LIMIT_API_REQUESTS="1000"
SECURITY_HEADERS_ENABLED="false"
CORS_ALLOW_ORIGINS="*"
```

#### Production Template (.env.production.template)
```bash
# SECURITY: Replace all placeholder values before deployment

# Core settings (REQUIRED)
API_KEY="REPLACE_WITH_SECURE_API_KEY"
DATABASE_URL="REPLACE_WITH_PRODUCTION_DATABASE_URL"
JWT_SECRET_KEY="REPLACE_WITH_JWT_SECRET"

# Server settings
HOST="0.0.0.0"
PORT="8002"
LOG_LEVEL="INFO"
RELOAD="false"

# Security settings
SECURITY_HEADERS_ENABLED="true"
RATE_LIMIT_API_REQUESTS="100"
RATE_LIMIT_AUTH_REQUESTS="10"

# Performance settings
WEB_CONCURRENCY="4"
DB_POOL_SIZE="20"
CACHE_MAX_SIZE="5000"
CACHE_BACKEND="redis"
REDIS_URL="REPLACE_WITH_REDIS_URL"

# Monitoring settings
METRICS_ENABLED="true"
LOG_TO_FILE="true"
LOG_FILE_PATH="/var/log/profile-api/production.log"
```

## 🛡️ Security Considerations

### Sensitive Configuration

**Never commit these to version control:**
- `API_KEY`
- `JWT_SECRET_KEY`
- `DATABASE_URL` (with credentials)
- `REDIS_URL` (with password)
- Email passwords
- Cloud service credentials

### Secure Configuration Practices

```bash
# Use environment variables for secrets
export API_KEY="$(cat /run/secrets/api_key)"

# Use secret management services
export API_KEY="$(aws secretsmanager get-secret-value --secret-id profile-api-key --query SecretString --output text)"

# Validate configuration on startup
export VALIDATE_CONFIG_ON_STARTUP="true"

# Enable configuration audit logging
export LOG_CONFIG_CHANGES="true"
```

### Production Security Checklist

- [ ] **API_KEY**: Generated with sufficient entropy (32+ characters)
- [ ] **JWT_SECRET_KEY**: 256-bit cryptographically secure key
- [ ] **DATABASE_URL**: Uses encrypted connections (SSL/TLS)
- [ ] **REDIS_URL**: Includes authentication credentials
- [ ] **File Permissions**: Configuration files have restricted access (600)
- [ ] **Environment Isolation**: Separate configs for dev/staging/prod
- [ ] **Secret Rotation**: Regular rotation of all secrets
- [ ] **Configuration Backup**: Secure backup of configuration templates

## 📚 Configuration Reference Summary

### Quick Reference Table

| Category | Variable | Default | Required | Description |
|----------|----------|---------|----------|-------------|
| **Core** | API_KEY | - | ✅ | Primary authentication key |
| **Core** | DATABASE_URL | sqlite:///./profiles.db | ✅ | Database connection string |
| **Core** | HOST | 0.0.0.0 | ❌ | Server bind address |
| **Core** | PORT | 8002 | ❌ | Server port |
| **Core** | LOG_LEVEL | INFO | ❌ | Logging verbosity |
| **Security** | JWT_SECRET_KEY | auto-generated | ❌ | JWT signing key |
| **Security** | JWT_ACCESS_TOKEN_EXPIRE | 3600 | ❌ | Access token lifetime |
| **Security** | RATE_LIMIT_API_REQUESTS | 100 | ❌ | API rate limit |
| **Cache** | CACHE_BACKEND | memory | ❌ | Cache storage backend |
| **Cache** | CACHE_MAX_SIZE | 2000 | ❌ | Maximum cache items |
| **Performance** | WEB_CONCURRENCY | 1 | ❌ | Worker processes |
| **Performance** | REQUEST_TIMEOUT | 30 | ❌ | Request timeout |
| **Monitoring** | METRICS_ENABLED | true | ❌ | Enable metrics collection |

### Configuration Validation Commands

```bash
# Validate current configuration
curl http://localhost:8002/healthcheck

# Check configuration endpoints
curl -H "X-API-Key: your-key" http://localhost:8002/status

# Test all components
curl http://localhost:8002/monitoring/detailed

# Validate environment variables
env | grep -E "(API_KEY|DATABASE_URL|LOG_LEVEL)" | wc -l
```

---

**⚠️ Important Notes**

1. **Always use secure values** in production environments
2. **Never commit secrets** to version control systems
3. **Validate configuration** before deployment
4. **Monitor configuration changes** in production
5. **Keep configuration templates** updated with new options

---

*This configuration guide is part of the comprehensive Profile API documentation suite. For additional information, see the [Security Guide](SECURITY_GUIDE.md) and [Operations Guide](OPERATIONS_GUIDE.md).*