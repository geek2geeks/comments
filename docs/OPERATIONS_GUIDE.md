# Profile API Operations Guide

> **Comprehensive operational procedures for the Profile & Engagement API**

This guide provides detailed procedures for monitoring, maintaining, troubleshooting, and operating the Profile API in production environments. It covers health monitoring, performance optimization, incident response, and routine maintenance tasks.

## 📊 Monitoring & Health Checks

### Health Check Endpoints

The Profile API provides multiple health check endpoints for different monitoring scenarios:

#### Basic Health Check (No Authentication)
```bash
# Simple connectivity test - Profile API
curl http://localhost:8002/healthcheck

# Profile API Tester connectivity
curl http://localhost:3001

# Internal Docker network health check
docker compose exec profile_api_tester curl http://profile_api:8002/healthcheck

# Expected response
{
  "status": "healthy",
  "timestamp": "2025-01-06T00:00:00.000000",
  "version": "1.0.0",
  "service": "Profile & Engagement API"
}
```

#### Ping Endpoint (No Authentication)
```bash
# Minimal latency test
curl http://localhost:8002/monitoring/ping

# Expected response
{
  "message": "pong",
  "timestamp": "2025-01-06T00:00:00.000000",
  "version": "1.0.0"
}
```

#### Detailed Health Check (No Authentication)
```bash
# Comprehensive component health
curl http://localhost:8002/monitoring/detailed

# Expected response structure
{
  "status": "healthy",  // healthy | degraded | unhealthy
  "timestamp": "2025-01-06T00:00:00.000000",
  "version": "1.0.0",
  "service": "Profile & Engagement API",
  "components": {
    "database": {
      "status": "healthy",
      "info": {
        "path": "/app/profiles.db",
        "size_mb": 2.5,
        "tables": 3
      }
    },
    "cache": {
      "status": "healthy",
      "total_items": 150,
      "memory_usage_mb": 45.2,
      "hit_rate": 0.85
    },
    "metrics": {
      "status": "healthy",
      "stats": {
        "requests_last_minute": 25,
        "avg_response_time_ms": 120.5,
        "system_cpu_percent": 15.3,
        "system_memory_percent": 62.8
      }
    }
  }
}
```

#### Service Status (Requires Authentication)
```bash
# Authenticated status with more details
curl -H "X-API-Key: your-api-key" http://localhost:8002/status

# Includes connection counts, session info, and security status
```

### Health Check Status Codes

| Status | Meaning | Action Required |
|--------|---------|----------------|
| `healthy` | All components operational | None |
| `degraded` | Some non-critical components failing | Monitor closely, investigate |
| `unhealthy` | Critical components failing | Immediate attention required |

### Monitoring Setup

#### Docker Compose Health Checks

The docker-compose.yml includes comprehensive health checks:

```yaml
# Profile API health check configuration
profile_api:
  healthcheck:
    test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8002/healthcheck', timeout=5)"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

**Check service health status:**
```bash
# View all service health
docker compose ps

# Check specific service health
docker compose ps profile_api
docker compose ps profile_api_tester

# View health check logs
docker inspect quizztok-profile-api --format='{{json .State.Health}}' | jq
```

#### Docker Health Checks (Standalone)
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8002/healthcheck', timeout=5)"
```

#### Kubernetes Liveness and Readiness Probes
```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: profile-api
        livenessProbe:
          httpGet:
            path: /healthcheck
            port: 8002
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /monitoring/detailed
            port: 8002
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          successThreshold: 1
          failureThreshold: 3
```

#### External Monitoring Integration
```bash
# Uptime monitoring (UptimeRobot, Pingdom, etc.)
curl -I http://your-domain.com/healthcheck
# Expected: HTTP 200 OK

# APM Integration (New Relic, DataDog, etc.)
curl http://your-domain.com/monitoring/metrics?time_window=5
# Returns JSON metrics for ingestion
```

## 📈 Performance Monitoring

### Metrics Collection

The Profile API automatically collects comprehensive performance metrics:

#### Request Metrics
- **Request duration** (average, min, max, P95, P99)
- **Requests per second** (RPS)
- **Status code distribution**
- **Endpoint usage patterns**
- **Error rates**

#### System Metrics
- **CPU utilization**
- **Memory usage**
- **Disk usage**
- **Network I/O**

#### Application Metrics
- **Cache hit rates**
- **Database query times**
- **Authentication success/failure rates**
- **Rate limiting violations**

### Accessing Metrics

#### Real-time Metrics API
```bash
# Get metrics for last 5 minutes
curl http://localhost:8002/monitoring/metrics?time_window=5

# Get metrics for last hour
curl http://localhost:8002/monitoring/metrics?time_window=60

# Example response structure
{
  "metrics": {
    "time_window_minutes": 5,
    "requests": {
      "total": 450,
      "avg_duration_ms": 125.3,
      "min_duration_ms": 12.1,
      "max_duration_ms": 892.4,
      "p95_duration_ms": 234.7,
      "p99_duration_ms": 445.2,
      "requests_per_second": 1.5,
      "status_codes": {
        "200": 420,
        "401": 15,
        "429": 12,
        "500": 3
      },
      "endpoints": {
        "GET /profile/*": 300,
        "POST /connect": 25,
        "GET /status": 100
      }
    },
    "system": {
      "cpu": {"percent": 15.3, "count": 4},
      "memory": {
        "total_bytes": 8589934592,
        "used_bytes": 5368709120,
        "percent": 62.5
      },
      "disk": {
        "total_bytes": 107374182400,
        "used_bytes": 32212254720,
        "percent": 30.0
      }
    },
    "counters": {
      "requests_total": 12450,
      "requests_get": 10230,
      "requests_post": 2220,
      "responses_200": 11890,
      "responses_401": 325,
      "responses_429": 180,
      "responses_500": 55
    }
  }
}
```

#### Cache Statistics
```bash
# Get cache performance metrics
curl http://localhost:8002/monitoring/cache/stats

# Response includes hit rates, memory usage, and item counts
{
  "cache_stats": {
    "total_items": 1250,
    "memory_usage_mb": 78.5,
    "hit_rate": 0.87,
    "miss_rate": 0.13,
    "evictions": 45,
    "expires": 123
  }
}
```

### Performance Alerts

#### Key Metrics to Monitor

| Metric | Threshold | Alert Level | Action |
|--------|-----------|-------------|--------|
| Average Response Time | > 500ms | Warning | Investigate slow queries |
| P95 Response Time | > 1000ms | Critical | Check system resources |
| Error Rate (5xx) | > 1% | Critical | Check logs immediately |
| Memory Usage | > 80% | Warning | Consider scaling |
| Memory Usage | > 90% | Critical | Scale immediately |
| CPU Usage | > 70% | Warning | Monitor load |
| CPU Usage | > 85% | Critical | Scale or optimize |
| Cache Hit Rate | < 70% | Warning | Review cache strategy |
| Disk Usage | > 80% | Warning | Clean up or expand |
| Disk Usage | > 90% | Critical | Immediate action required |

#### Alert Configuration Examples

**Prometheus Alert Rules:**
```yaml
groups:
- name: profile-api-alerts
  rules:
  - alert: HighResponseTime
    expr: profile_api_request_duration_p95 > 1000
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Profile API response time is high"
      
  - alert: HighErrorRate
    expr: rate(profile_api_requests_total{status=~"5.."}[5m]) > 0.01
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Profile API error rate is high"
```

## 🔧 Operational Procedures

### Service Management

#### Starting the Service

**Direct Python:**
```bash
cd profile_api/
python main.py
# Service starts on http://0.0.0.0:8002
```

**Using Setup Script:**
```bash
cd profile_api/
python setup_and_run.py
# Includes dependency checking and environment setup
```

**Docker:**
```bash
# Single container
docker run -d \
  --name profile-api \
  -p 8002:8002 \
  -e API_KEY="your-api-key" \
  -e DATABASE_URL="sqlite:///./profiles.db" \
  profile-api:latest

# Docker Compose
docker compose up profile_api -d
```

#### Stopping the Service

**Direct Process:**
```bash
# Find process
ps aux | grep "python main.py"

# Graceful shutdown
kill -TERM <pid>

# Force kill if needed
kill -KILL <pid>
```

**Docker:**
```bash
# Stop container
docker stop profile-api

# Remove container
docker rm profile-api
```

#### Service Status Verification

```bash
# Check if service is running
curl -f http://localhost:8002/healthcheck || echo "Service is down"

# Check process
ps aux | grep "python main.py" | grep -v grep

# Check Docker container
docker ps | grep profile-api

# Check listening ports
netstat -tlnp | grep :8002
```

### Log Management

#### Log Locations

**Docker Compose Deployment:**
```bash
# Container logs for Profile API
docker compose logs profile_api -f

# With timestamps
docker compose logs profile_api -f -t

# Last 100 lines
docker compose logs profile_api --tail=100

# All services logs
docker compose logs -f

# Profile API Tester logs
docker compose logs profile_api_tester -f

# Specific container logs (alternative)
docker logs quizztok-profile-api -f
docker logs quizztok-profile-api-tester -f
```

**Standalone Docker Deployment:**
```bash
# Container logs
docker logs profile-api -f

# With timestamps
docker logs profile-api -f -t

# Last 100 lines
docker logs profile-api --tail=100
```

**Direct Deployment:**
```bash
# Application logs (if configured)
tail -f /var/log/profile-api/app.log

# System logs
journalctl -u profile-api -f

# Python logs (default)
tail -f ./profile_api.log
```

#### Log Levels and Configuration

```bash
# Set log level via environment variable
export LOG_LEVEL="DEBUG"    # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Enable structured JSON logging
export LOG_FORMAT="json"

# Enable correlation ID tracking
export ENABLE_CORRELATION_ID="true"
```

#### Log Analysis

**Common Log Queries:**
```bash
# Find authentication failures
grep "Authentication failed" /var/log/profile-api/app.log

# Find rate limit violations
grep "Rate limit exceeded" /var/log/profile-api/app.log

# Find slow requests (>1000ms)
grep '"duration_ms":[0-9]\{4,\}' /var/log/profile-api/app.log

# Find 5xx errors
grep '"status_code":5[0-9][0-9]' /var/log/profile-api/app.log

# Get request volume by hour
grep "$(date '+%Y-%m-%d %H:')" /var/log/profile-api/app.log | wc -l
```

**Log Aggregation Tools:**
```bash
# Using jq for JSON logs
cat /var/log/profile-api/app.log | jq '.level' | sort | uniq -c

# Find errors in last hour
cat /var/log/profile-api/app.log | \
  jq 'select(.timestamp > "'$(date -d '1 hour ago' -Iseconds)'")' | \
  jq 'select(.level == "ERROR")'
```

### Database Management

#### Database Health

```bash
# Check database file
ls -la profile_api/profiles.db

# Check database size
du -h profile_api/profiles.db

# SQLite integrity check
sqlite3 profile_api/profiles.db "PRAGMA integrity_check;"

# Check table structure
sqlite3 profile_api/profiles.db ".schema"

# Check record counts
sqlite3 profile_api/profiles.db "
  SELECT 
    name,
    (SELECT COUNT(*) FROM ' || name || ') as count
  FROM sqlite_master 
  WHERE type='table' AND name NOT LIKE 'sqlite_%';
"
```

#### Database Backup

```bash
# Create backup
sqlite3 profile_api/profiles.db ".backup backups/profiles_$(date +%Y%m%d_%H%M%S).db"

# Automated backup script
#!/bin/bash
BACKUP_DIR="/app/backups"
DB_FILE="/app/profiles.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_FILE" ".backup $BACKUP_DIR/profiles_$TIMESTAMP.db"

# Keep only last 30 days of backups
find "$BACKUP_DIR" -name "profiles_*.db" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/profiles_$TIMESTAMP.db"
```

#### Database Recovery

```bash
# Restore from backup
cp backups/profiles_20250106_120000.db profile_api/profiles.db

# Verify restored database
sqlite3 profile_api/profiles.db "PRAGMA integrity_check;"

# Restart service to reload
systemctl restart profile-api
```

#### Database Maintenance

```bash
# Vacuum to reclaim space
sqlite3 profile_api/profiles.db "VACUUM;"

# Analyze for query optimization
sqlite3 profile_api/profiles.db "ANALYZE;"

# Check WAL file size
ls -la profile_api/profiles.db-wal

# Checkpoint WAL if large
sqlite3 profile_api/profiles.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

### Cache Management

#### Cache Operations

```bash
# Get cache statistics
curl http://localhost:8002/monitoring/cache/stats

# Clear entire cache (requires admin API key)
curl -X POST -H "X-API-Key: admin-key" \
  http://localhost:8002/cache/clear

# Clear specific cache keys
curl -X DELETE -H "X-API-Key: admin-key" \
  http://localhost:8002/cache/key/profile:username

# Get cache key info
curl -H "X-API-Key: admin-key" \
  http://localhost:8002/cache/key/profile:username
```

#### Cache Tuning

**Environment Variables:**
```bash
# Cache configuration
export CACHE_MAX_SIZE="2000"        # Maximum items
export CACHE_MAX_MEMORY_MB="200"    # Memory limit
export CACHE_DEFAULT_TTL="300"      # 5 minutes default TTL
export CACHE_CLEANUP_INTERVAL="60"  # Cleanup every minute
```

**Monitoring Cache Performance:**
```bash
# Watch cache hit rate
watch -n 5 'curl -s http://localhost:8002/monitoring/cache/stats | jq .cache_stats.hit_rate'

# Monitor cache memory usage
watch -n 10 'curl -s http://localhost:8002/monitoring/cache/stats | jq .cache_stats.memory_usage_mb'
```

## 🚨 Troubleshooting Guide

### Common Issues and Solutions

#### 1. Service Won't Start

**Symptoms:**
- Process exits immediately
- Connection refused on port 8002
- Import errors in logs

**Diagnostic Steps:**
```bash
# Check if port is already in use
netstat -tlnp | grep :8002

# Check Python dependencies
python -c "import fastapi, uvicorn; print('Dependencies OK')"

# Check environment variables
env | grep -E "(API_KEY|DATABASE_URL|LOG_LEVEL)"

# Test database connection
python -c "
import sqlite3
conn = sqlite3.connect('profiles.db')
print('Database connection OK')
conn.close()
"
```

**Common Solutions:**
```bash
# Kill process using the port
sudo lsof -ti:8002 | xargs kill -9

# Install missing dependencies
pip install -r requirements.txt

# Set required environment variables
export API_KEY="dev-api-key-12345"
export DATABASE_URL="sqlite:///./profiles.db"

# Check file permissions
chmod 644 profiles.db
chmod 755 $(dirname profiles.db)
```

#### 2. High Response Times

**Symptoms:**
- API requests taking >1000ms
- Timeout errors
- High CPU usage

**Diagnostic Steps:**
```bash
# Check current metrics
curl http://localhost:8002/monitoring/metrics | jq .metrics.requests

# Monitor system resources
top -p $(pgrep -f "python main.py")

# Check database locks
sqlite3 profiles.db "PRAGMA database_list;"

# Look for slow queries in logs
grep -E '"duration_ms":[5-9][0-9]{2,}' /var/log/profile-api/app.log
```

**Solutions:**
```bash
# Restart service to clear temporary issues
systemctl restart profile-api

# Clear cache if corruption suspected
curl -X POST -H "X-API-Key: admin-key" http://localhost:8002/cache/clear

# Vacuum database to improve performance
sqlite3 profiles.db "VACUUM; ANALYZE;"

# Check for resource limits
ulimit -a

# Scale resources if needed (Docker)
docker update --memory=2g --cpus=2 profile-api
```

#### 3. Authentication Failures

**Symptoms:**
- 401 Unauthorized responses ("AUTHENTICATION_REQUIRED")
- "Invalid API key" errors  
- JWT token errors
- 403 Forbidden responses ("INSUFFICIENT_PERMISSIONS")
- Connection failures to TikTok Live endpoints

**Common Error Messages:**
```json
{"error": "AUTHENTICATION_REQUIRED", "message": "Valid authentication credentials required"}
{"error": "INSUFFICIENT_PERMISSIONS", "message": "Insufficient permissions for this endpoint"}
{"detail": "Method Not Allowed"}
```

**Diagnostic Steps:**
```bash
# 1. Check API key format and environment configuration
echo "API_KEY in environment: $API_KEY"
echo "Expected development key: dev-api-key-12345"

# 2. Test development authentication
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8002/status

# 3. Test connection endpoint with proper method
curl -X POST -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-12345" \
  -d '{"session_id":"test","username":"test-user"}' \
  http://localhost:8002/connect

# 4. Check service logs for authentication details
docker compose logs profile_api --tail=20 | grep -E "(auth|API key|user)"

# 5. Test standard pk_ prefixed key
echo $API_KEY | grep -E '^pk_[A-Za-z0-9_-]+$' || echo "Not standard format"

# 6. Check JWT generation (if using token auth)
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}'
```

**Development Authentication Troubleshooting:**

**Problem**: Authentication fails with development key `dev-api-key-12345`
```bash
# Check environment variable is set
docker compose exec profile_api env | grep API_KEY

# Verify development user creation in logs
docker compose logs profile_api | grep "Created dev user"

# Test development authentication flow
curl -v -H "X-API-Key: dev-api-key-12345" http://localhost:8002/healthcheck
```

**Problem**: "INSUFFICIENT_PERMISSIONS" error on /connect endpoint
```bash
# Verify permissions granted to development key
docker compose logs profile_api | grep -E "(permissions|wildcard)"

# Check if dev user was created with SERVICE role
docker compose logs profile_api | grep -E "(dev user|SERVICE)"

# Test with specific permission requirement
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8002/profile/test-user
```

**Problem**: Cache API errors in /connect endpoint
```bash
# Check for cache-related errors
docker compose logs profile_api | grep -E "(cache|TypeError)"

# Verify cache operations are working
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8002/monitoring/cache/stats
```

**Solutions:**
```bash
# 1. Fix development authentication setup
export API_KEY="dev-api-key-12345"
docker compose restart profile_api

# 2. Generate new standard API key for production
python -c "
import secrets
print(f'pk_{secrets.token_urlsafe(32)}')
"

# 3. Fix authentication middleware if dev user creation fails
# Check core/auth.py for verify_api_key and authenticate_api_key methods

# 4. Fix cache API calls if TypeError occurs
# Ensure cache.get(key) and cache.set(key, value, ttl) have correct parameters

# 5. Reset authentication state
docker compose restart profile_api

# 6. Clear JWT blacklist if corrupted
# (Restart service to clear in-memory blacklist)

# 7. Verify Docker environment configuration
docker compose config | grep -A 5 -B 5 API_KEY
```

**Environment-specific Solutions:**
```bash
# Development Environment
# - Use API_KEY=dev-api-key-12345 in docker-compose.yml
# - Restart profile_api service after changes
# - Check logs for "Created dev user for environment API key"

# Production Environment  
# - Use API_KEY=pk_<secure-random-string>
# - Generate keys via API endpoints with proper authentication
# - Never use development keys in production
```

**Testing Authentication Fix:**
```bash
# Complete authentication test sequence
echo "Testing development authentication..."

# 1. Verify environment
echo "API_KEY: $(docker compose exec profile_api env | grep API_KEY)"

# 2. Test health endpoint (no auth required)
curl -s http://localhost:8002/healthcheck | jq .status

# 3. Test authenticated endpoint
curl -s -H "X-API-Key: dev-api-key-12345" http://localhost:8002/status | jq .

# 4. Test connect endpoint with proper request format
curl -s -X POST -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-12345" \
  -d '{"session_id":"test-auth","username":"test-user"}' \
  http://localhost:8002/connect | jq .

echo "If all tests return valid JSON, authentication is working correctly."
```

#### 4. Database Issues

**Symptoms:**
- "Database is locked" errors
- Corruption messages
- SQLite errors

**Diagnostic Steps:**
```bash
# Check database integrity
sqlite3 profiles.db "PRAGMA integrity_check;"

# Check for locks
sqlite3 profiles.db "PRAGMA busy_timeout = 5000; SELECT 1;"

# Check WAL file size
ls -la profiles.db-wal profiles.db-shm

# Check file permissions
ls -la profiles.db
```

**Solutions:**
```bash
# Unlock database
sqlite3 profiles.db "PRAGMA wal_checkpoint(RESTART);"

# Restore from backup if corrupted
cp backups/profiles_latest.db profiles.db

# Fix permissions
chown app:app profiles.db
chmod 644 profiles.db

# Restart service
systemctl restart profile-api
```

#### 5. Memory Issues

**Symptoms:**
- Out of memory errors
- Service becoming unresponsive
- High memory usage

**Diagnostic Steps:**
```bash
# Check memory usage
ps aux | grep "python main.py"
free -h

# Check cache memory usage
curl http://localhost:8002/monitoring/cache/stats | jq .cache_stats.memory_usage_mb

# Monitor memory over time
watch -n 5 'ps --no-headers -o rss -p $(pgrep -f "python main.py")'
```

**Solutions:**
```bash
# Clear cache
curl -X POST -H "X-API-Key: admin-key" http://localhost:8002/cache/clear

# Reduce cache size
export CACHE_MAX_MEMORY_MB="100"
systemctl restart profile-api

# Add swap if needed (Linux)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Scale container resources (Docker)
docker update --memory=1g profile-api
```

### Error Code Reference

#### HTTP Status Codes

| Code | Meaning | Common Causes | Resolution |
|------|---------|---------------|------------|
| 400 | Bad Request | Invalid JSON, missing parameters | Check request format |
| 401 | Unauthorized | Invalid/missing API key or JWT | Verify authentication |
| 403 | Forbidden | Insufficient permissions | Check user role/permissions |
| 404 | Not Found | Invalid endpoint or resource | Verify URL |
| 413 | Request Too Large | Request exceeds size limit | Reduce request size |
| 415 | Unsupported Media Type | Wrong Content-Type header | Use application/json |
| 429 | Too Many Requests | Rate limit exceeded | Wait and retry with backoff |
| 500 | Internal Server Error | Application error | Check logs, restart service |
| 502 | Bad Gateway | Reverse proxy issues | Check proxy configuration |
| 503 | Service Unavailable | Service overloaded/down | Check service health |

#### Application Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `RATE_LIMIT_EXCEEDED` | Too many requests | Wait for rate limit reset |
| `AUTHENTICATION_FAILED` | Invalid credentials | Check API key/JWT |
| `VALIDATION_ERROR` | Input validation failed | Fix request data |
| `DATABASE_ERROR` | Database operation failed | Check database health |
| `CACHE_ERROR` | Cache operation failed | Clear cache or restart |
| `CONNECTION_ERROR` | TikTok connection failed | Check TikTok service |

### Performance Optimization

#### Identifying Performance Bottlenecks

```bash
# Monitor request patterns
curl http://localhost:8002/monitoring/metrics | \
  jq '.metrics.requests.endpoints' | \
  jq 'to_entries | sort_by(.value) | reverse'

# Find slowest endpoints
grep -E '"duration_ms":[0-9]{3,}' /var/log/profile-api/app.log | \
  jq -r '"\(.endpoint) \(.duration_ms)ms"' | \
  sort -k2 -nr | head -10

# Check system resource usage
iostat -x 1 5    # Disk I/O
vmstat 1 5       # Memory and CPU
sar -n DEV 1 5   # Network I/O
```

#### Optimization Strategies

**Database Optimization:**
```bash
# Add indexes for common queries
sqlite3 profiles.db "
  CREATE INDEX IF NOT EXISTS idx_username ON profiles(username);
  CREATE INDEX IF NOT EXISTS idx_created_at ON profiles(created_at);
"

# Optimize database
sqlite3 profiles.db "VACUUM; ANALYZE;"
```

**Cache Optimization:**
```bash
# Increase cache size for high-traffic
export CACHE_MAX_SIZE="5000"
export CACHE_MAX_MEMORY_MB="500"

# Adjust TTL based on usage patterns
export CACHE_DEFAULT_TTL="600"  # 10 minutes for stable data
```

**Application Optimization:**
```bash
# Increase worker processes (if using Gunicorn)
export WEB_CONCURRENCY="4"

# Adjust rate limits for legitimate traffic
export RATE_LIMIT_API_REQUESTS="200"
export RATE_LIMIT_API_WINDOW="60"
```

## 🔄 Maintenance Procedures

### Daily Maintenance

#### Health Check Routine
```bash
#!/bin/bash
# Daily health check script

echo "=== Profile API Daily Health Check ==="
echo "Date: $(date)"

# Basic connectivity - Profile API
echo -n "Profile API health check: "
if curl -s -f http://localhost:8002/healthcheck > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
fi

# Basic connectivity - Profile API Tester
echo -n "Profile API Tester health check: "
if curl -s -f http://localhost:3001 > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
fi

# Detailed health
echo -n "Detailed health check: "
HEALTH=$(curl -s http://localhost:8002/monitoring/detailed | jq -r .status)
if [ "$HEALTH" = "healthy" ]; then
    echo "✓ PASS"
elif [ "$HEALTH" = "degraded" ]; then
    echo "⚠ DEGRADED"
else
    echo "✗ FAIL ($HEALTH)"
fi

# Inter-service communication test
echo -n "Inter-service communication: "
if docker compose exec profile_api_tester curl -s -f http://profile_api:8002/healthcheck > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
fi

# Performance metrics
echo "Performance metrics (last 24 hours):"
METRICS=$(curl -s http://localhost:8002/monitoring/metrics?time_window=1440)
echo "$METRICS" | jq '.metrics.requests | {
    total: .total,
    avg_duration_ms: .avg_duration_ms,
    requests_per_second: .requests_per_second,
    error_rate: (.status_codes."500" // 0) / .total
}'

# Database size
echo -n "Database size: "
du -h profiles.db

# Cache statistics
echo "Cache performance:"
curl -s http://localhost:8002/monitoring/cache/stats | jq '.cache_stats | {
    hit_rate: .hit_rate,
    memory_usage_mb: .memory_usage_mb,
    total_items: .total_items
}'
```

### Weekly Maintenance

#### Database Maintenance
```bash
#!/bin/bash
# Weekly database maintenance

echo "=== Weekly Database Maintenance ==="

# Backup database
BACKUP_FILE="backups/profiles_weekly_$(date +%Y%m%d).db"
sqlite3 profiles.db ".backup $BACKUP_FILE"
echo "Database backed up to: $BACKUP_FILE"

# Check database integrity
echo -n "Database integrity check: "
INTEGRITY=$(sqlite3 profiles.db "PRAGMA integrity_check;")
if [ "$INTEGRITY" = "ok" ]; then
    echo "✓ PASS"
else
    echo "✗ FAIL: $INTEGRITY"
fi

# Optimize database
echo "Optimizing database..."
sqlite3 profiles.db "VACUUM; ANALYZE;"
echo "Database optimization complete"

# Check WAL file size
WAL_SIZE=$(stat -c%s profiles.db-wal 2>/dev/null || echo "0")
if [ "$WAL_SIZE" -gt 10485760 ]; then  # 10MB
    echo "WAL file is large ($WAL_SIZE bytes), checkpointing..."
    sqlite3 profiles.db "PRAGMA wal_checkpoint(TRUNCATE);"
fi

# Clean old backups (keep 4 weeks)
find backups/ -name "profiles_*.db" -mtime +28 -delete
echo "Cleaned old backups"
```

#### Log Rotation
```bash
#!/bin/bash
# Log rotation script

LOG_DIR="/var/log/profile-api"
DATE=$(date +%Y%m%d)

# Rotate application logs
if [ -f "$LOG_DIR/app.log" ]; then
    mv "$LOG_DIR/app.log" "$LOG_DIR/app.log.$DATE"
    gzip "$LOG_DIR/app.log.$DATE"
    
    # Restart service to create new log file
    systemctl reload profile-api
fi

# Clean logs older than 30 days
find "$LOG_DIR" -name "*.log.*.gz" -mtime +30 -delete

echo "Log rotation complete"
```

### Monthly Maintenance

#### Security Review
```bash
#!/bin/bash
# Monthly security review

echo "=== Monthly Security Review ==="

# Check for authentication failures
echo "Authentication failures (last 30 days):"
grep "Authentication failed" /var/log/profile-api/app.log.* 2>/dev/null | wc -l

# Check for rate limit violations
echo "Rate limit violations (last 30 days):"
grep "Rate limit exceeded" /var/log/profile-api/app.log.* 2>/dev/null | wc -l

# Check for suspicious activity
echo "Suspicious activity detections (last 30 days):"
grep "Suspicious activity detected" /var/log/profile-api/app.log.* 2>/dev/null | wc -l

# Review API key usage
echo "Active API keys:"
# This would query the auth service for active keys
curl -H "X-API-Key: admin-key" http://localhost:8002/auth/api-keys | \
    jq '.keys | length'

# Check SSL certificate expiry (if using HTTPS)
echo "SSL certificate status:"
echo | openssl s_client -connect your-domain.com:443 2>/dev/null | \
    openssl x509 -noout -dates
```

#### Performance Review
```bash
#!/bin/bash
# Monthly performance review

echo "=== Monthly Performance Review ==="

# Average response times by endpoint
echo "Average response times by endpoint (last 30 days):"
# Analyze logs to calculate endpoint performance
grep '"duration_ms":' /var/log/profile-api/app.log.* | \
    jq -r '"\(.endpoint) \(.duration_ms)"' | \
    awk '{sum[$1]+=$2; count[$1]++} END {for(i in sum) print i, sum[i]/count[i]"ms"}' | \
    sort -k2 -nr

# Memory usage trends
echo "Peak memory usage (last 30 days):"
# This would typically come from monitoring system
echo "Analysis requires historical monitoring data"

# Database growth
echo "Database size growth:"
ls -la profiles.db
```

### Disaster Recovery

#### Backup Strategy

**Automated Backup Script:**
```bash
#!/bin/bash
# Automated backup with retention

BACKUP_DIR="/app/backups"
REMOTE_BACKUP_DIR="s3://your-bucket/profile-api-backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create local backup
sqlite3 profiles.db ".backup $BACKUP_DIR/profiles_$DATE.db"

# Compress backup
gzip "$BACKUP_DIR/profiles_$DATE.db"

# Upload to cloud storage
aws s3 cp "$BACKUP_DIR/profiles_$DATE.db.gz" "$REMOTE_BACKUP_DIR/"

# Local retention (keep 7 days)
find "$BACKUP_DIR" -name "profiles_*.db.gz" -mtime +7 -delete

# Remote retention (keep 90 days)
aws s3 ls "$REMOTE_BACKUP_DIR/" --recursive | \
    grep "profiles_" | \
    awk '$1 < "'$(date -d '90 days ago' '+%Y-%m-%d')'" {print $4}' | \
    xargs -I {} aws s3 rm "s3://your-bucket/{}"

echo "Backup completed: profiles_$DATE.db.gz"
```

#### Recovery Procedures

**Full Service Recovery:**
```bash
#!/bin/bash
# Full service recovery procedure

echo "=== Profile API Recovery Procedure ==="

# 1. Stop the service
echo "Stopping Profile API service..."
systemctl stop profile-api

# 2. Backup current state (if possible)
if [ -f "profiles.db" ]; then
    cp profiles.db "profiles.db.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Current database backed up"
fi

# 3. Restore database from backup
echo "Restoring database from backup..."
LATEST_BACKUP=$(ls -t backups/profiles_*.db.gz | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    gunzip -c "$LATEST_BACKUP" > profiles.db
    echo "Database restored from: $LATEST_BACKUP"
else
    echo "ERROR: No backup found!"
    exit 1
fi

# 4. Verify database integrity
echo "Verifying database integrity..."
INTEGRITY=$(sqlite3 profiles.db "PRAGMA integrity_check;")
if [ "$INTEGRITY" != "ok" ]; then
    echo "ERROR: Database integrity check failed: $INTEGRITY"
    exit 1
fi

# 5. Set correct permissions
chown app:app profiles.db
chmod 644 profiles.db

# 6. Start the service
echo "Starting Profile API service..."
systemctl start profile-api

# 7. Wait for service to be ready
echo "Waiting for service to be ready..."
for i in {1..30}; do
    if curl -s -f http://localhost:8002/healthcheck > /dev/null; then
        echo "Service is ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# 8. Verify service health
echo "Verifying service health..."
curl http://localhost:8002/monitoring/detailed | jq .status

echo "Recovery procedure completed"
```

---

**📋 Quick Reference Commands**

```bash
# Service Status
systemctl status profile-api
curl http://localhost:8002/healthcheck

# View Logs - Docker Compose
docker compose logs profile_api -f
docker compose logs profile_api_tester -f
docker compose logs -f  # All services

# View Logs - Standalone Docker
docker logs quizztok-profile-api -f
journalctl -u profile-api -f  # If using systemd

# Performance Check
curl http://localhost:8002/monitoring/metrics
curl http://localhost:8002/monitoring/cache/stats

# Service Status Check
docker compose ps
docker compose exec profile_api python -c "from core.database import get_database_info; print(get_database_info())"

# Database Maintenance
docker compose exec profile_api sqlite3 profiles.db "VACUUM; ANALYZE;"
docker compose exec profile_api sqlite3 profiles.db "PRAGMA wal_checkpoint(TRUNCATE);"

# PostgreSQL Maintenance (if using shared Quizztok DB)
docker compose exec postgres psql -U quizztok_user -d quizztok_db -c "VACUUM ANALYZE;"

# Emergency Stop
systemctl stop profile-api
docker stop profile-api

# Emergency Restart
systemctl restart profile-api
docker restart profile-api
```

**📞 Emergency Contacts**

- **System Administrator**: admin@example.com
- **Database Administrator**: dba@example.com  
- **Security Team**: security@example.com
- **On-Call Engineer**: +1-555-ONCALL

---

*This operations guide is part of the comprehensive Profile API documentation suite. For additional information, see the [Security Guide](SECURITY_GUIDE.md) and [Deployment Guide](DEPLOYMENT_GUIDE.md).*