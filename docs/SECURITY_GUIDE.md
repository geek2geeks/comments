# Profile API Security Guide

> **Enterprise-grade security documentation for the Profile & Engagement API**

This guide provides comprehensive security information for implementing, configuring, and maintaining the Profile API in production environments. The service implements multiple layers of security including dual authentication, rate limiting, input validation, and comprehensive audit logging.

## 🔐 Authentication Architecture

The Profile API implements a sophisticated dual authentication system that supports both API keys and JWT tokens, providing flexibility for different use cases while maintaining enterprise-grade security.

### Authentication Flow Overview

```mermaid
graph TB
    A[Client Request] --> B{Has X-API-Key Header?}
    B -->|Yes| C[Validate API Key]
    B -->|No| D{Has Authorization Header?}
    D -->|Yes| E[Validate JWT Token]
    D -->|No| F[Return 401 Unauthorized]
    C -->|Valid| G[Check Permissions]
    C -->|Invalid| F
    E -->|Valid| G
    E -->|Invalid| F
    G -->|Allowed| H[Process Request]
    G -->|Denied| I[Return 403 Forbidden]
```

## 🗝️ API Key Authentication

API keys provide a simple, secure way to authenticate service-to-service communication and long-lived integrations.

### API Key Format

API keys follow a standardized format for easy identification:
- **Prefix**: `pk_` (identifies as Profile API key)
- **Payload**: 32 bytes of URL-safe base64 encoded random data
- **Example**: `pk_abcdef1234567890ABCDEF1234567890abcdef1234567890`

### API Key Management

#### Generating API Keys

```bash
# Via API endpoint (requires existing authentication)
curl -X POST http://localhost:8002/auth/api-keys/generate \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Service Key",
    "permissions": ["read", "write", "connect"],
    "expires_in_days": 90
  }'
```

#### API Key Storage

- **Client Side**: Store securely in environment variables or secret management systems
- **Server Side**: Only salted SHA-256 hashes are stored, never the raw key
- **Database**: Keys are indexed by hash for fast lookup while maintaining security

#### API Key Permissions

API keys support granular permissions:

| Permission | Description | Endpoints |
|------------|-------------|-----------|
| `read` | Read-only access | `/profile/*`, `/status` |
| `write` | Data modification | `/profiles/revalidate` |
| `connect` | Connection management | `/connect`, `/disconnect`, `/ws/*` |
| `admin` | Administrative access | `/cache/*`, `/metrics/*` |
| `*` | All permissions | All endpoints |

#### Using API Keys

```bash
# API key in header (recommended)
curl -H "X-API-Key: pk_your-api-key-here" http://localhost:8002/profile/username

# API key in query parameter (WebSocket only)
wscat -c "ws://localhost:8002/ws/comments/session123?api_key=pk_your-api-key-here"
```

### Development API Key Authentication

For development and testing environments, the Profile API supports a special authentication mechanism using environment-based API keys that don't follow the standard `pk_` prefix format.

#### Development Key Configuration

```bash
# Environment variable in docker-compose.yml
environment:
  - API_KEY=dev-api-key-12345
```

#### How Development Authentication Works

1. **Environment Key Check**: When an API key is provided that doesn't start with `pk_`, the system checks if it matches the `API_KEY` environment variable
2. **Automatic User Creation**: If the environment key matches, a development user is automatically created with SERVICE role privileges
3. **Wildcard Permissions**: Development keys receive `["*"]` permissions, granting access to all endpoints
4. **Session Management**: Development users are created on-demand and persist for the service lifetime

#### Development Authentication Flow

```mermaid
graph TB
    A[API Key: dev-api-key-12345] --> B{Starts with 'pk_'?}
    B -->|No| C{Matches API_KEY env var?}
    B -->|Yes| D[Standard API Key Validation]
    C -->|Yes| E[Create Development APIKey Object]
    C -->|No| F[Return None - Authentication Failed]
    E --> G{Dev user exists?}
    G -->|No| H[Auto-create dev user with SERVICE role]
    G -->|Yes| I[Use existing dev user]
    H --> J[Grant wildcard permissions]
    I --> J
    J --> K[Authentication Successful]
```

#### Development Key Security Considerations

**✅ Advantages:**
- Simplified development setup without key generation
- No need for complex key management in dev environments
- Automatic user provisioning reduces setup friction
- Full API access for comprehensive testing

**⚠️ Security Implications:**
- **Development only**: Never use environment-based keys in production
- **Plaintext storage**: Environment keys are stored as plaintext
- **Wide permissions**: Wildcard access increases attack surface
- **Persistent sessions**: Dev users persist until service restart

#### Production Migration

When moving to production, replace development authentication:

```bash
# 1. Generate proper API key
curl -X POST http://localhost:8002/auth/api-keys/generate \
  -H "Authorization: Bearer admin-token" \
  -d '{"name": "Production Key", "permissions": ["read", "write", "connect"]}'

# 2. Update environment configuration
# Remove: API_KEY=dev-api-key-12345
# Add: API_KEY=pk_generated_production_key_here

# 3. Update client applications
export PROFILE_API_KEY="pk_generated_production_key_here"
```

#### Testing Development Authentication

```bash
# Test development key authentication
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8002/connect \
  -X POST -H "Content-Type: application/json" \
  -d '{"session_id": "test-session", "username": "test-user"}'

# Expected response: 200 OK with connection details
# Expected logs: "Created dev user for environment API key"
```

### API Key Security Best Practices

#### Generation and Distribution
- **Generate on server**: Never generate API keys client-side
- **Unique per service**: Create separate keys for each service/environment
- **Secure transmission**: Only transmit keys over HTTPS/TLS
- **Immediate storage**: Store in secure location immediately after generation

#### Storage and Management
- **Environment variables**: Store keys in environment variables, never in code
- **Secret management**: Use dedicated secret management services in production
- **Regular rotation**: Rotate keys every 90 days or after security incidents
- **Monitor usage**: Track API key usage for anomaly detection

```bash
# Environment variable storage (recommended)
export PROFILE_API_KEY="pk_your-secure-api-key-here"

# Application usage
curl -H "X-API-Key: $PROFILE_API_KEY" http://localhost:8002/status
```

#### Access Control
- **Principle of least privilege**: Grant only necessary permissions
- **Environment separation**: Use different keys for dev/staging/production
- **Team access**: Create separate keys for different teams/applications
- **Audit trail**: Log all API key usage for security monitoring

## 🎫 JWT Token Authentication

JWT (JSON Web Token) authentication provides stateless, cryptographically signed tokens ideal for user sessions and temporary access.

### JWT Token Structure

The Profile API uses RS256 (RSA + SHA-256) signed JWTs with the following structure:

#### Access Token Payload
```json
{
  "sub": "user-id-12345",
  "username": "john.doe",
  "email": "john@example.com", 
  "role": "user",
  "type": "access",
  "exp": 1640995200,
  "iat": 1640991600,
  "jti": "unique-token-id-for-revocation"
}
```

#### Refresh Token Payload
```json
{
  "sub": "user-id-12345",
  "type": "refresh",
  "exp": 1641598400,
  "iat": 1640991600,
  "jti": "unique-refresh-token-id"
}
```

### JWT Authentication Flow

#### 1. User Registration
```bash
curl -X POST http://localhost:8002/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe",
    "email": "john@example.com",
    "password": "SecurePassword123!"
  }'
```

#### 2. User Login
```bash
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe",
    "password": "SecurePassword123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### 3. Using Access Tokens
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8002/profile/username
```

#### 4. Token Refresh
```bash
curl -X POST http://localhost:8002/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
  }'
```

### JWT Security Features

#### Token Expiration
- **Access tokens**: 1 hour (configurable via `ACCESS_TOKEN_EXPIRE`)
- **Refresh tokens**: 7 days (configurable via `REFRESH_TOKEN_EXPIRE`) 
- **Automatic cleanup**: Expired tokens are automatically rejected

#### Token Revocation
- **JWT ID (jti)**: Each token has a unique identifier for revocation
- **Blacklist**: Revoked tokens are added to an in-memory blacklist
- **Logout endpoint**: Immediately revokes access tokens

```bash
# Revoke current token
curl -X POST http://localhost:8002/auth/logout \
  -H "Authorization: Bearer your-access-token"
```

#### Signature Verification
- **Algorithm**: HMAC-SHA256 (HS256) for symmetric keys
- **Secret rotation**: JWT secrets can be rotated without downtime
- **Signature validation**: All tokens are cryptographically verified

## 🛡️ Security Middleware Stack

The Profile API implements multiple security middleware layers that work together to provide comprehensive protection.

### 1. Rate Limiting Middleware

Implements token bucket algorithm with different limits for different endpoint types:

#### Rate Limit Rules

| Rule Type | Requests/Window | Window Duration | Endpoints |
|-----------|----------------|-----------------|-----------|
| `api` | 100 | 60 seconds | General API calls |
| `auth` | 10 | 60 seconds | `/auth/*`, `/login` |
| `connect` | 5 | 300 seconds | `/connect`, `/disconnect` |
| `websocket` | 20 | 60 seconds | `/ws/*` |

#### Rate Limit Headers

All responses include rate limiting information:

```http
HTTP/1.1 200 OK
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

#### Rate Limit Exceeded Response

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests",
  "retry_after": 45,
  "remaining": 0
}
```

#### Configuration

```bash
# Environment variables for rate limiting
export RATE_LIMIT_API_REQUESTS=100
export RATE_LIMIT_API_WINDOW=60
export RATE_LIMIT_AUTH_REQUESTS=10
export RATE_LIMIT_AUTH_WINDOW=60
export RATE_LIMIT_CONNECT_REQUESTS=5
export RATE_LIMIT_CONNECT_WINDOW=300
```

### 2. Enhanced Authentication Middleware

Processes both API key and JWT authentication with role-based permissions:

#### Excluded Paths (No Authentication Required)
- `/health`, `/healthcheck`, `/ping`
- `/monitoring/*`
- `/docs`, `/redoc`, `/openapi.json`
- `/auth/login`, `/auth/register`

#### Permission Mapping

| Endpoint Pattern | Required Permission | Description |
|------------------|-------------------|-------------|
| `/connect`, `/disconnect` | `connect` | Connection management |
| `/profile/*` | `read` | Profile data access |
| `/profiles/revalidate` | `write` | Data modification |
| `/status` | `read` | Service status |
| `/sessions` | `read` | Session information |
| `/cache/*` | `admin` | Cache management |
| `/metrics` | `admin` | System metrics |

### 3. Input Validation Middleware

Validates all incoming requests for security and data integrity:

#### Request Size Limits
- **Maximum request size**: 10MB (configurable)
- **Automatic rejection**: Requests exceeding limit return 413 status

#### Content Type Validation
- **Allowed types**: `application/json`, `multipart/form-data`
- **Charset validation**: UTF-8 encoding enforcement
- **Boundary validation**: Multipart boundary size limits

#### Header Validation
- **User-Agent**: Format and length validation (logged but not blocked)
- **Referer**: Domain whitelist validation for CSRF protection
- **Content-Length**: Numeric validation and range checking

### 4. Security Headers Middleware

Adds comprehensive security headers to all responses:

```http
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
X-Frame-Options: DENY  
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
X-Correlation-ID: abc123def456
```

### 5. Security Audit Middleware

Monitors and logs suspicious activity patterns:

#### Suspicious Pattern Detection
- **Path traversal**: `../` patterns
- **XSS attempts**: `<script`, `javascript:` patterns
- **SQL injection**: `union select`, `drop table` patterns  
- **Code injection**: `exec(`, `eval(` patterns

#### Audit Logging

All requests are logged with security context:

```json
{
  "timestamp": "2025-01-06T00:00:00.000Z",
  "level": "INFO",
  "message": "GET /profile/username - 200",
  "client_ip": "192.168.1.100",
  "method": "GET", 
  "path": "/profile/username",
  "status_code": 200,
  "duration_ms": 45.2,
  "user_agent": "Mozilla/5.0...",
  "correlation_id": "abc123def456"
}
```

## 🔒 Password Security

The Profile API implements enterprise-grade password security practices:

### Password Requirements

- **Minimum length**: 8 characters
- **Maximum length**: 128 characters
- **Complexity requirements**:
  - At least one uppercase letter (A-Z)
  - At least one lowercase letter (a-z)
  - At least one digit (0-9)
  - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

### Password Hashing

- **Algorithm**: bcrypt with adaptive cost
- **Salt**: Unique random salt for each password
- **Cost factor**: Automatically adjusted based on server performance
- **Storage**: Only hashes stored, never plaintext passwords

### Password Validation Example

```python
# Valid passwords
"SecurePass123!"  # ✓ All requirements met
"MyP@ssw0rd2025"  # ✓ All requirements met

# Invalid passwords  
"password"        # ✗ Missing uppercase, digits, special chars
"PASSWORD123"     # ✗ Missing lowercase, special chars
"Pass123"         # ✗ Too short (< 8 characters)
```

## 🚨 Security Monitoring

### Real-time Monitoring

The Profile API provides comprehensive security monitoring capabilities:

#### Authentication Monitoring
```bash
# Monitor authentication failures
curl -H "X-API-Key: admin-key" http://localhost:8002/monitoring/auth/failures

# Monitor suspicious activity
curl -H "X-API-Key: admin-key" http://localhost:8002/monitoring/security/alerts
```

#### Rate Limit Monitoring
```bash
# Check current rate limits
curl -H "X-API-Key: admin-key" http://localhost:8002/monitoring/rate-limits

# Monitor rate limit violations
curl -H "X-API-Key: admin-key" http://localhost:8002/monitoring/rate-limits/violations
```

### Security Metrics

The service tracks critical security metrics:

- **Authentication success/failure rates**
- **API key usage patterns**  
- **Rate limit violations by IP/endpoint**
- **Suspicious activity detection**
- **Token revocation events**
- **Password change frequency**

## 🔧 Security Configuration

### Environment Variables

#### Authentication Configuration
```bash
# JWT Configuration
JWT_SECRET_KEY="your-256-bit-secret-key-here"
JWT_ACCESS_TOKEN_EXPIRE="3600"      # 1 hour in seconds
JWT_REFRESH_TOKEN_EXPIRE="604800"   # 7 days in seconds

# API Key Configuration  
API_KEY_DEFAULT_EXPIRE="7776000"    # 90 days in seconds
API_KEY_MAX_PER_USER="10"           # Maximum keys per user

# Password Configuration
PASSWORD_MIN_LENGTH="8"
PASSWORD_MAX_LENGTH="128"
PASSWORD_REQUIRE_COMPLEXITY="true"
```

#### Rate Limiting Configuration
```bash
# Default API rate limits
RATE_LIMIT_API_REQUESTS="100"
RATE_LIMIT_API_WINDOW="60"

# Authentication rate limits (stricter)
RATE_LIMIT_AUTH_REQUESTS="10"
RATE_LIMIT_AUTH_WINDOW="60"

# Connection rate limits (very strict)
RATE_LIMIT_CONNECT_REQUESTS="5"  
RATE_LIMIT_CONNECT_WINDOW="300"

# WebSocket rate limits
RATE_LIMIT_WEBSOCKET_REQUESTS="20"
RATE_LIMIT_WEBSOCKET_WINDOW="60"
```

#### Security Headers Configuration
```bash
# Security headers (boolean flags)
SECURITY_HEADERS_ENABLED="true"
SECURITY_HEADERS_HSTS="true"
SECURITY_HEADERS_CSP="true"
SECURITY_HEADERS_FRAME_OPTIONS="DENY"

# Content Security Policy
CSP_DEFAULT_SRC="'self'"
CSP_SCRIPT_SRC="'self'"
CSP_STYLE_SRC="'self' 'unsafe-inline'"
```

#### Audit and Logging Configuration
```bash
# Security audit settings
SECURITY_AUDIT_ENABLED="true"
SECURITY_AUDIT_LOG_LEVEL="INFO"
SECURITY_SUSPICIOUS_PATTERN_DETECTION="true"

# Correlation ID tracking
CORRELATION_ID_ENABLED="true"
CORRELATION_ID_HEADER="X-Correlation-ID"
```

### Production Security Checklist

#### Pre-deployment Security Review

- [ ] **JWT secrets**: Generate strong, unique secrets (256-bit minimum)
- [ ] **API keys**: Implement secure generation and storage
- [ ] **Database**: Enable encryption at rest and in transit
- [ ] **HTTPS**: Configure TLS 1.3 with strong cipher suites
- [ ] **Headers**: Enable all security headers
- [ ] **Rate limiting**: Configure appropriate limits for expected traffic
- [ ] **Monitoring**: Set up security event alerting
- [ ] **Backup**: Implement secure backup procedures
- [ ] **Access control**: Review all endpoint permissions
- [ ] **Input validation**: Test with security scanners

#### Post-deployment Security Verification

- [ ] **Authentication**: Verify both API key and JWT auth work
- [ ] **Rate limiting**: Test limits are enforced correctly  
- [ ] **HTTPS**: Verify TLS configuration with SSL Labs
- [ ] **Headers**: Check security headers with online scanners
- [ ] **Logging**: Confirm audit logs are being generated
- [ ] **Monitoring**: Test security alert notifications
- [ ] **Backup**: Verify backup and restore procedures
- [ ] **Penetration testing**: Conduct security assessment

## 🔍 Security Testing

### Authentication Testing

#### API Key Testing
```bash
# Test valid API key
curl -H "X-API-Key: pk_valid_key_here" http://localhost:8002/status
# Expected: 200 OK

# Test invalid API key  
curl -H "X-API-Key: invalid_key" http://localhost:8002/status
# Expected: 401 Unauthorized

# Test missing API key
curl http://localhost:8002/status
# Expected: 401 Unauthorized
```

#### JWT Testing
```bash
# Test valid JWT token
curl -H "Authorization: Bearer valid_jwt_token" http://localhost:8002/profile/test
# Expected: 200 OK

# Test expired JWT token
curl -H "Authorization: Bearer expired_jwt_token" http://localhost:8002/profile/test  
# Expected: 401 Unauthorized

# Test malformed JWT token
curl -H "Authorization: Bearer invalid.jwt.token" http://localhost:8002/profile/test
# Expected: 401 Unauthorized
```

### Rate Limiting Testing

```bash
# Test rate limiting with rapid requests
for i in {1..150}; do
  curl -H "X-API-Key: test_key" http://localhost:8002/status &
done
wait
# Expected: First 100 succeed (200), remainder fail (429)

# Test rate limit headers
curl -v -H "X-API-Key: test_key" http://localhost:8002/status
# Expected: X-RateLimit-Remaining and X-RateLimit-Reset headers
```

### Security Headers Testing

```bash
# Test security headers presence
curl -v http://localhost:8002/health | grep -i "x-\|strict\|content-security"
# Expected: All security headers present

# Test HTTPS redirect (production)
curl -v http://your-domain.com/health
# Expected: 301/302 redirect to HTTPS
```

### Input Validation Testing

```bash
# Test request size limits
dd if=/dev/zero bs=1M count=15 | curl -X POST -H "Content-Type: application/json" --data-binary @- http://localhost:8002/test-endpoint
# Expected: 413 Request Too Large

# Test malformed JSON
curl -X POST -H "Content-Type: application/json" -d "invalid json" http://localhost:8002/auth/login
# Expected: 400 Bad Request
```

## 🚨 Incident Response

### Security Incident Types

#### 1. Authentication Bypass
**Indicators:**
- Successful requests without valid authentication
- Multiple failed authentication attempts followed by success
- Access to restricted endpoints by unauthorized users

**Response:**
1. Immediately rotate JWT secrets and API keys
2. Review authentication middleware logs
3. Check for code vulnerabilities in auth system
4. Monitor for continued unauthorized access

#### 2. Rate Limit Bypass
**Indicators:**
- Requests exceeding configured rate limits
- Distributed requests from multiple IPs
- Unusual traffic patterns

**Response:**
1. Enable additional IP-based blocking
2. Reduce rate limit thresholds temporarily
3. Analyze traffic patterns for DDoS indicators
4. Review rate limiting middleware configuration

#### 3. Data Exfiltration
**Indicators:**
- Large volume of profile data requests
- Access to multiple user profiles by single API key
- Unusual data access patterns

**Response:**
1. Revoke suspicious API keys immediately  
2. Enable additional access logging
3. Review data access permissions
4. Notify affected users if necessary

#### 4. Injection Attacks
**Indicators:**
- Suspicious patterns in request logs
- Database errors in application logs
- Unusual characters in request parameters

**Response:**
1. Block attacking IP addresses
2. Review input validation effectiveness
3. Check database for unauthorized changes
4. Update security patterns in audit middleware

### Emergency Procedures

#### Immediate Response (0-30 minutes)
1. **Assess impact**: Determine scope and severity
2. **Contain threat**: Block attacking IPs, revoke compromised keys
3. **Preserve evidence**: Capture logs and system state
4. **Notify stakeholders**: Alert security team and management

#### Short-term Response (30 minutes - 4 hours)
1. **Investigate root cause**: Analyze logs and system configuration
2. **Implement fixes**: Patch vulnerabilities or misconfigurations
3. **Monitor for recurrence**: Watch for continued attack attempts
4. **Document findings**: Record incident details and response actions

#### Long-term Response (4+ hours)
1. **Security review**: Comprehensive review of affected systems
2. **Process improvement**: Update procedures based on lessons learned
3. **User communication**: Notify users if their data was affected
4. **Compliance reporting**: File required regulatory reports

### Logging and Forensics

#### Critical Log Sources
- **Authentication logs**: `/logs/auth.log`
- **Security audit logs**: `/logs/security.log`
- **Rate limiting logs**: `/logs/rate_limit.log`
- **Application logs**: `/logs/profile_api.log`

#### Log Analysis Commands
```bash
# Find authentication failures
grep "Authentication failed" /logs/auth.log | tail -100

# Find rate limit violations  
grep "Rate limit exceeded" /logs/rate_limit.log | tail -100

# Find suspicious activity
grep "Suspicious activity detected" /logs/security.log | tail -100

# Find API key usage patterns
grep "API key.*used successfully" /logs/auth.log | awk '{print $6}' | sort | uniq -c
```

## 📋 Security Maintenance

### Regular Security Tasks

#### Daily
- [ ] Review security logs for suspicious activity
- [ ] Monitor authentication failure rates
- [ ] Check rate limiting effectiveness
- [ ] Verify backup integrity

#### Weekly  
- [ ] Review API key usage patterns
- [ ] Update security pattern detection rules
- [ ] Test security alert notifications
- [ ] Analyze security metrics trends

#### Monthly
- [ ] Rotate JWT secrets
- [ ] Review and update rate limit configurations
- [ ] Conduct security configuration review
- [ ] Update security documentation

#### Quarterly
- [ ] Comprehensive security audit
- [ ] Penetration testing
- [ ] Security training review
- [ ] Update incident response procedures

### Security Updates

#### Dependency Updates
```bash
# Check for security updates
pip-audit --format=json

# Update dependencies
pip install --upgrade -r requirements.txt

# Verify no regressions
pytest tests/security/
```

#### Configuration Updates
```bash
# Review security configuration
python -c "from core.auth import get_auth_service; print('Auth service initialized')"

# Test all authentication methods
pytest tests/auth/ -v

# Verify rate limiting
pytest tests/rate_limiting/ -v
```

## 📚 Additional Security Resources

### Security Standards Compliance
- **OWASP API Security Top 10**: Full compliance with latest guidelines
- **NIST Cybersecurity Framework**: Implementation of security controls
- **ISO 27001**: Information security management best practices

### Security Tools and Services
- **Static Analysis**: CodeQL, Semgrep for code security scanning
- **Dynamic Testing**: OWASP ZAP, Burp Suite for runtime testing  
- **Dependency Scanning**: pip-audit, Safety for vulnerability detection
- **Secret Management**: HashiCorp Vault, AWS Secrets Manager

### Security Training Resources
- **OWASP API Security**: https://owasp.org/api-security-project/
- **JWT Security**: https://auth0.com/blog/a-look-at-the-latest-draft-for-jwt-bcp/
- **Rate Limiting**: https://cloud.google.com/architecture/rate-limiting-strategies-techniques

---

**⚠️ Critical Security Notice**

This security guide contains sensitive security information. Ensure proper access controls are in place before sharing this document. Never commit secrets, API keys, or passwords to version control systems.

**📞 Security Contact**

For security-related questions or to report vulnerabilities:
- **Email**: security@example.com
- **PGP Key**: Available on company website
- **Response Time**: 24 hours for critical issues

---

*This security guide is part of the comprehensive Profile API documentation suite. For additional information, see the [API Documentation](API_DOCUMENTATION.md) and [Deployment Guide](DEPLOYMENT_GUIDE.md).*