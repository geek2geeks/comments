# Profile API Deployment Guide

> **Production-ready deployment instructions for the Profile & Engagement API**

This guide provides comprehensive deployment instructions for various environments, from local development to production-scale deployments with high availability and monitoring.

## 📋 Table of Contents

- [Quick Start Deployment](#quick-start-deployment)
- [Development Environment](#development-environment)
- [Production Deployment](#production-deployment)
- [Container Orchestration](#container-orchestration)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Security Considerations](#security-considerations)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

## 🚀 Quick Start Deployment

### Option 1: Docker Compose (Recommended)

Deploy the entire Quizztok microservices stack with Profile API:

```bash
# Clone repository
git clone <repository-url>
cd quizztok-final

# Start full microservices stack (includes Profile API Tester)
docker compose --profile dev up -d

# Or start Profile API with core dependencies only
docker compose --profile dev up profile_api postgres redis -d

# Verify deployment
curl http://localhost:8002/healthcheck
curl http://localhost:3001  # Profile API Tester
```

**Available Services:**

| Service | Port | URL | Status |
|---------|------|-----|--------|
| **Profile API** | 8002 | http://localhost:8002 | Core service |
| **Profile API Tester** | 3001 | http://localhost:3001 | Testing interface |
| Game Backend | 8000 | http://localhost:8000 | Main game logic |
| Frontend | 3000 | http://localhost:3000 | Quiz application |
| PostgreSQL | 5432 | localhost:5432 | Database |
| Redis | 6379 | localhost:6379 | Session storage |

**Docker Profiles Available:**
```bash
# Development stack (Profile API + testing tools)
docker compose --profile dev up -d

# Debug stack (includes Adminer + Dozzle logs)
docker compose --profile debug up -d

# Frontend only
docker compose --profile frontend up -d

# Full stack (all services)
docker compose --profile full up -d
```

### Option 2: Standalone Container

Run Profile API as a standalone container:

```bash
# Build the image
cd profile_api/
docker build -t profile-api:latest .

# Run with basic configuration
docker run -d \
  --name profile-api \
  -p 8002:8002 \
  -e API_KEY="your-secure-api-key" \
  -e DATABASE_URL="sqlite:///./profiles.db" \
  profile-api:latest

# Check status
docker logs profile-api
curl http://localhost:8002/healthcheck
```

## 🛠️ Development Environment

### Local Python Setup

For active development and debugging:

```bash
# Prerequisites
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
cd profile_api/
pip install -r requirements.txt

# Set development environment variables
export API_KEY="dev-api-key-12345"
export DATABASE_URL="sqlite:///./profiles.db"
export LOG_LEVEL="DEBUG"
export JWT_SECRET_KEY="dev-jwt-secret-key-change-in-production"

# Start development server
python main.py
```

### Development with Hot Reload

```bash
# Alternative: Use uvicorn directly for hot reload
cd profile_api/
uvicorn main:app --reload --host 0.0.0.0 --port 8002

# Or use the setup script
python setup_and_run.py
```

### Docker Development

For containerized development with hot reload:

```bash
# From project root
docker compose --profile dev up profile_api

# View logs
docker compose logs profile_api -f

# Access container for debugging
docker compose exec profile_api bash
```

## 🏭 Production Deployment

### Production Docker Setup

#### 1. Environment Preparation

Create production environment file:

```bash
# Create .env.production
cat > .env.production << EOF
# Security
API_KEY="$(openssl rand -hex 32)"
JWT_SECRET_KEY="$(openssl rand -hex 32)"

# Database (PostgreSQL recommended for production)
DATABASE_URL="postgresql://profile_user:$(openssl rand -hex 16)@postgres:5432/profile_db"

# Performance
LOG_LEVEL="INFO"
RATE_LIMIT_REQUESTS="200"
RATE_LIMIT_WINDOW="60"

# Monitoring
ENABLE_METRICS="true"
HEALTH_CHECK_INTERVAL="30"

# TikTok Integration (Optional)
TIKTOK_USERNAME="your_production_username"
EOF
```

#### 2. Production Container Build

```bash
# Build optimized production image
docker build \
  --target production \
  --build-arg BUILD_ENV=production \
  -t profile-api:v1.0.0 \
  ./profile_api/

# Tag for registry
docker tag profile-api:v1.0.0 your-registry.com/profile-api:v1.0.0

# Push to registry
docker push your-registry.com/profile-api:v1.0.0
```

#### 3. Production Deployment

```bash
# Deploy with production configuration
docker run -d \
  --name profile-api-prod \
  --restart unless-stopped \
  -p 8002:8002 \
  --env-file .env.production \
  -v profile_data:/app/data \
  -v profile_logs:/app/logs \
  --memory="512m" \
  --cpus="1.0" \
  profile-api:v1.0.0

# Verify deployment
curl -f http://localhost:8002/healthcheck || echo "Health check failed"
```

### Production with Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  profile-api:
    image: profile-api:v1.0.0
    container_name: profile-api-prod
    ports:
      - "8002:8002"
    environment:
      - API_KEY=${API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - LOG_LEVEL=INFO
    volumes:
      - profile_data:/app/data
      - profile_logs:/app/logs
    depends_on:
      - postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
        reservations:
          memory: 256M
          cpus: '0.5'
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8002/healthcheck', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres:
    image: postgres:15
    container_name: profile-postgres
    environment:
      - POSTGRES_DB=profile_db
      - POSTGRES_USER=profile_user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U profile_user -d profile_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: profile-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

volumes:
  profile_data:
  profile_logs:
  postgres_data:
  redis_data:

networks:
  default:
    name: profile-network
```

Deploy:

```bash
# Start production stack
docker compose -f docker-compose.prod.yml up -d

# Monitor startup
docker compose -f docker-compose.prod.yml logs -f profile-api
```

## ☁️ Cloud Platform Deployment

### AWS ECS Deployment

#### 1. Task Definition

```json
{
  "family": "profile-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "profile-api",
      "image": "your-registry.com/profile-api:v1.0.0",
      "portMappings": [
        {
          "containerPort": 8002,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:profile-api-secrets"
        },
        {
          "name": "DATABASE_URL", 
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:profile-db-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/profile-api",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "python -c \"import requests; requests.get('http://localhost:8002/healthcheck', timeout=5)\""
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

#### 2. Service Configuration

```bash
# Create ECS service
aws ecs create-service \
  --cluster profile-cluster \
  --service-name profile-api-service \
  --task-definition profile-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-abcdef],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:region:account:targetgroup/profile-api-tg,containerName=profile-api,containerPort=8002

# Create Profile API Tester service (optional for staging)
aws ecs create-service \
  --cluster profile-cluster \
  --service-name profile-api-tester-service \
  --task-definition profile-api-tester:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-abcdef],assignPublicIp=ENABLED}"
```

### Google Cloud Run Deployment

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/profile-api:v1.0.0

# Deploy to Cloud Run
gcloud run deploy profile-api \
  --image gcr.io/PROJECT_ID/profile-api:v1.0.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 10 \
  --set-env-vars LOG_LEVEL=INFO \
  --set-secrets API_KEY=profile-api-key:latest,DATABASE_URL=profile-db-url:latest
```

### Kubernetes Deployment

#### 1. Namespace and ConfigMap

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: profile-api

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: profile-api-config
  namespace: profile-api
data:
  LOG_LEVEL: "INFO"
  RATE_LIMIT_REQUESTS: "200"
  RATE_LIMIT_WINDOW: "60"
```

#### 2. Secret Management

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: profile-api-secrets
  namespace: profile-api
type: Opaque
stringData:
  API_KEY: "your-production-api-key"
  JWT_SECRET_KEY: "your-production-jwt-secret"
  DATABASE_URL: "postgresql://user:pass@postgres:5432/profile_db"
```

#### 3. Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: profile-api
  namespace: profile-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: profile-api
  template:
    metadata:
      labels:
        app: profile-api
    spec:
      containers:
      - name: profile-api
        image: profile-api:v1.0.0
        ports:
        - containerPort: 8002
        envFrom:
        - configMapRef:
            name: profile-api-config
        - secretRef:
            name: profile-api-secrets
        livenessProbe:
          httpGet:
            path: /healthcheck
            port: 8002
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /healthcheck
            port: 8002
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: profile-api-service
  namespace: profile-api
spec:
  selector:
    app: profile-api
  ports:
  - port: 80
    targetPort: 8002
  type: LoadBalancer
```

Deploy:

```bash
# Apply all configurations
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f deployment.yaml

# Check deployment status
kubectl get pods -n profile-api
kubectl get services -n profile-api

# View logs
kubectl logs -l app=profile-api -n profile-api -f
```

## 🗃️ Database Setup

### PostgreSQL Production Setup

#### 1. Docker PostgreSQL

```bash
# Run PostgreSQL container
docker run -d \
  --name profile-postgres \
  -e POSTGRES_DB=profile_db \
  -e POSTGRES_USER=profile_user \
  -e POSTGRES_PASSWORD=secure_password \
  -v postgres_data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:15

# Initialize database
docker exec -it profile-postgres psql -U profile_user -d profile_db -c "
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(50) DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  key_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255),
  permissions TEXT[],
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP,
  last_used TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
"
```

#### 2. Managed Database Services

**AWS RDS:**
```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier profile-api-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username profile_user \
  --master-user-password SecurePassword123 \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-12345678 \
  --db-subnet-group-name profile-subnet-group \
  --backup-retention-period 7 \
  --storage-encrypted
```

**Google Cloud SQL:**
```bash
# Create Cloud SQL instance
gcloud sql instances create profile-api-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=20GB \
  --backup-start-time=03:00
```

### Database Migration

```python
# migration_script.py
"""
Database migration script for Profile API
"""
import os
import psycopg2
from sqlalchemy import create_engine, text

def run_migration():
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Create tables if they don't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                key_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                permissions TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
        """))
        
        conn.commit()
        print("Database migration completed successfully")

if __name__ == "__main__":
    run_migration()
```

## 🔒 Security Considerations

### SSL/TLS Configuration

#### 1. Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/profile-api
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    ssl_certificate /path/to/certificate.pem;
    ssl_certificate_key /path/to/private-key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
}
```

#### 2. Let's Encrypt SSL

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d api.yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Firewall Configuration

```bash
# UFW Firewall Rules
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 8002/tcp    # Profile API (if direct access needed)
sudo ufw enable

# iptables rules for Docker
sudo iptables -I INPUT -p tcp --dport 8002 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 5432 -j DROP  # Block external DB access
```

### Secret Management

#### 1. Docker Secrets

```bash
# Create secrets
echo "your-production-api-key" | docker secret create api_key -
echo "your-jwt-secret" | docker secret create jwt_secret -

# Use in docker-compose.yml
services:
  profile-api:
    secrets:
      - api_key
      - jwt_secret
    environment:
      - API_KEY_FILE=/run/secrets/api_key
      - JWT_SECRET_KEY_FILE=/run/secrets/jwt_secret

secrets:
  api_key:
    external: true
  jwt_secret:
    external: true
```

#### 2. HashiCorp Vault Integration

```python
# vault_integration.py
import hvac
import os

def get_secrets_from_vault():
    client = hvac.Client(url=os.getenv('VAULT_URL'))
    client.token = os.getenv('VAULT_TOKEN')
    
    secret = client.secrets.kv.v2.read_secret_version(
        path='profile-api/production'
    )
    
    return secret['data']['data']

# Usage in main.py
if os.getenv('USE_VAULT') == 'true':
    secrets = get_secrets_from_vault()
    os.environ['API_KEY'] = secrets['api_key']
    os.environ['JWT_SECRET_KEY'] = secrets['jwt_secret']
```

## 📊 Monitoring & Logging

### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'profile-api'
    static_configs:
      - targets: ['localhost:8002']
    metrics_path: '/monitoring/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Profile API Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "stat", 
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

### Centralized Logging

#### 1. ELK Stack

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:7.17.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  logstash:
    image: docker.elastic.co/logstash/logstash:7.17.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  profile-api:
    # ... existing config
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  elasticsearch_data:
```

#### 2. Structured Logging Configuration

```python
# Update main.py for structured logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

## 💾 Backup & Recovery

### Database Backup

#### 1. Automated Backup Script

```bash
#!/bin/bash
# backup_database.sh

set -e

DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="profile_db"
DB_USER="profile_user"
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="profile_db_backup_$DATE.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Perform backup
PGPASSWORD=$DB_PASSWORD pg_dump \
    -h $DB_HOST \
    -p $DB_PORT \
    -U $DB_USER \
    -d $DB_NAME \
    --no-password \
    --verbose \
    --clean \
    --if-exists \
    > $BACKUP_DIR/$BACKUP_FILE

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE

# Remove backups older than 30 days
find $BACKUP_DIR -name "profile_db_backup_*.sql.gz" -mtime +30 -delete

echo "Database backup completed: $BACKUP_FILE.gz"
```

#### 2. Cron Schedule

```bash
# Add to crontab
0 2 * * * /path/to/backup_database.sh >> /var/log/backup.log 2>&1
```

### Container Volume Backup

```bash
#!/bin/bash
# backup_volumes.sh

BACKUP_DIR="/backups/volumes"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup profile data
docker run --rm \
    -v profile_data:/data \
    -v $BACKUP_DIR:/backup \
    alpine tar czf /backup/profile_data_$DATE.tar.gz -C /data .

# Backup logs
docker run --rm \
    -v profile_logs:/logs \
    -v $BACKUP_DIR:/backup \
    alpine tar czf /backup/profile_logs_$DATE.tar.gz -C /logs .

echo "Volume backups completed"
```

### Disaster Recovery Plan

1. **Database Recovery:**
   ```bash
   # Restore from backup
   PGPASSWORD=$DB_PASSWORD psql \
       -h $DB_HOST \
       -p $DB_PORT \
       -U $DB_USER \
       -d $DB_NAME \
       < backup_file.sql
   ```

2. **Service Recovery:**
   ```bash
   # Restore service from backup
   docker compose -f docker-compose.prod.yml down
   
   # Restore volumes
   docker run --rm -v profile_data:/data -v /backups:/backup alpine \
       tar xzf /backup/profile_data_20250106_020000.tar.gz -C /data
   
   # Restart services
   docker compose -f docker-compose.prod.yml up -d
   ```

3. **Health Check:**
   ```bash
   # Verify service health
   curl -f http://localhost:8002/healthcheck
   curl -H "X-API-Key: $API_KEY" http://localhost:8002/status
   ```

## 🔧 Troubleshooting

### Common Issues

#### 1. Service Won't Start

**Symptoms:**
- Container exits immediately
- Health checks failing
- Connection refused errors

**Diagnosis:**
```bash
# Check container logs
docker logs profile-api

# Check resource usage
docker stats profile-api

# Verify environment variables
docker exec profile-api env | grep -E "(API_KEY|DATABASE_URL)"
```

**Solutions:**
- Verify API_KEY is set and not empty
- Check DATABASE_URL format and connectivity
- Ensure port 8002 is available
- Verify sufficient memory allocation (minimum 256MB)

#### 2. Database Connection Issues

**Symptoms:**
- "Connection refused" errors
- Authentication failures
- Timeout errors

**Diagnosis:**
```bash
# Test database connectivity
docker exec profile-api python -c "
from core.database import test_connection
test_connection()
"

# Check PostgreSQL status
docker exec postgres pg_isready -U profile_user -d profile_db
```

**Solutions:**
- Verify PostgreSQL is running and accessible
- Check username/password in DATABASE_URL
- Ensure database exists and user has permissions
- For SQLite, verify write permissions on data directory

#### 3. Authentication Problems

**Symptoms:**
- 401 Unauthorized errors
- Invalid API key messages
- JWT token rejected

**Diagnosis:**
```bash
# Test authentication
curl -H "X-API-Key: your-key" http://localhost:8002/status
curl -H "Authorization: Bearer your-jwt" http://localhost:8002/status

# Check API key format
echo $API_KEY | wc -c  # Should be > 20 characters
```

**Solutions:**
- Regenerate API keys using admin endpoints
- Verify JWT_SECRET_KEY is set consistently
- Check for special characters in environment variables
- Ensure API keys start with "pk_" prefix

#### 4. Performance Issues

**Symptoms:**
- Slow response times
- High memory usage
- Rate limiting errors

**Diagnosis:**
```bash
# Check system metrics
curl http://localhost:8002/monitoring/metrics

# Monitor resource usage
docker stats profile-api

# Check cache performance
curl http://localhost:8002/monitoring/cache/stats
```

**Solutions:**
- Increase container memory limits
- Tune rate limiting configuration
- Enable Redis for distributed caching
- Optimize database queries and connections

### Health Check Commands

```bash
# Basic health check
curl -f http://localhost:8002/healthcheck || echo "FAIL: Basic health check"

# Detailed health check
curl -s http://localhost:8002/monitoring/detailed | jq '.status' || echo "FAIL: Detailed health check"

# API functionality test
curl -f -H "X-API-Key: $API_KEY" http://localhost:8002/status || echo "FAIL: API authentication"

# Database connectivity test
docker exec profile-api python -c "
from core.database import get_database_info
info = get_database_info()
print('DB Status:', info.get('connection_healthy', 'Unknown'))
" || echo "FAIL: Database connectivity"
```

### Log Analysis

```bash
# Filter error logs
docker logs profile-api 2>&1 | grep -i error

# Check authentication logs
docker logs profile-api 2>&1 | grep "authentication"

# Monitor real-time logs
docker logs profile-api -f --tail 100

# Export logs for analysis
docker logs profile-api > profile-api-logs-$(date +%Y%m%d).log
```

## 📞 Support & Maintenance

### Regular Maintenance Tasks

1. **Weekly:**
   - Review application logs for errors
   - Check database backup integrity
   - Monitor resource usage trends
   - Update security patches

2. **Monthly:**
   - Rotate API keys if needed
   - Review and clean old logs
   - Database maintenance (VACUUM, ANALYZE)
   - Performance optimization review

3. **Quarterly:**
   - Security audit and penetration testing
   - Disaster recovery testing
   - Dependency updates and security scanning
   - Capacity planning review

### Monitoring Checklist

- [ ] Service health checks passing
- [ ] Database connectivity verified
- [ ] Authentication endpoints responding
- [ ] WebSocket connections working
- [ ] Log aggregation functioning
- [ ] Backup processes completing
- [ ] SSL certificates not expiring
- [ ] Resource usage within limits

---

**📝 Last Updated:** January 2025  
**🔧 Version:** 1.0.0  
**📊 Status:** Production Ready

For deployment assistance or issues, please refer to:
- **[API Documentation](API_DOCUMENTATION.md)** - Complete endpoint specifications
- **[Security Guide](SECURITY_GUIDE.md)** - Security best practices
- **[Operations Guide](OPERATIONS_GUIDE.md)** - Monitoring and troubleshooting