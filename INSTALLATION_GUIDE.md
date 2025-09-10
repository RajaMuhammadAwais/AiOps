# AIOps Installation Guide

<!-- Badges -->
[![Build Status](https://github.com/RajaMuhammadAwais/AiOps/actions/workflows/ci-cd.yaml/badge.svg)](https://github.com/RajaMuhammadAwais/AiOps/actions)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/RajaMuhammadAwais/AiOps)](./License.md)
[![Contributors](https://img.shields.io/github/contributors/RajaMuhammadAwais/AiOps)](https://github.com/RajaMuhammadAwais/AiOps/graphs/contributors)
[![Issues](https://img.shields.io/github/issues/RajaMuhammadAwais/AiOps)](https://github.com/RajaMuhammadAwais/AiOps/issues)

## Quick Start

For new users, run the automated installation script:

```bash
curl -fsSL https://raw.githubusercontent.com/your-repo/aiops/main/install_aiops.sh | bash
```

Or download and run manually:

```bash
wget https://raw.githubusercontent.com/your-repo/aiops/main/install_aiops.sh
chmod +x install_aiops.sh
./install_aiops.sh
```

## System Requirements

### Operating System Support
- **Linux**: Ubuntu 20.04+, CentOS 8+, RHEL 8+, Amazon Linux 2
- **macOS**: 10.15+ (Catalina and newer)
- **Windows**: Windows 10+ with WSL2

### Hardware Requirements
- **Minimum**: 4 CPU cores, 8GB RAM, 50GB storage
- **Recommended**: 8 CPU cores, 16GB RAM, 200GB SSD storage
- **Production**: 16+ CPU cores, 32GB+ RAM, 500GB+ NVMe storage

### Software Dependencies
- **Python**: 3.11 or newer
- **Git**: For source code management
- **curl/wget**: For downloading components
- **systemd**: For service management (Linux)

## Installation Methods

### Method 1: Automated Script Installation (Recommended)

The installation script automatically:
- Detects your operating system
- Installs required dependencies
- Sets up Python virtual environment
- Configures system services
- Initializes the database
- Starts the AIOps services

```bash
# Download and run installer
curl -fsSL https://install.aiops.example.com | bash

# Or with custom installation directory
curl -fsSL https://install.aiops.example.com | bash -s -- --install-dir=/opt/aiops
```

### Method 2: Manual Installation

#### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    git curl wget build-essential libpq-dev redis-server postgresql
```

**CentOS/RHEL:**
```bash
sudo dnf install -y python3.11 python3.11-devel git curl wget \
    gcc postgresql-devel redis postgresql-server
```

**macOS:**
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.11 git postgresql redis
```

#### Step 2: Create Installation Directory
```bash
sudo mkdir -p /opt/aiops
sudo chown $USER:$USER /opt/aiops
cd /opt/aiops
```

#### Step 3: Clone Repository
```bash
git clone https://github.com/your-org/aiops-system.git .
```

#### Step 4: Setup Python Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

#### Step 5: Configure Services
```bash
# Copy configuration templates
cp config/aiops.conf.example config/aiops.conf
cp config/.env.example .env

# Edit configuration files
nano .env
nano config/aiops.conf
```

#### Step 6: Initialize Database
```bash
# PostgreSQL setup
sudo -u postgres createuser aiops
sudo -u postgres createdb aiops_db -O aiops
sudo -u postgres psql -c "ALTER USER aiops PASSWORD 'your_password';"

# Initialize AIOps database
python manage.py migrate
python manage.py init-data
```

#### Step 7: Install System Services
```bash
# Install systemd services (Linux)
sudo cp scripts/aiops-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aiops-engine aiops-dashboard aiops-worker
sudo systemctl start aiops-engine aiops-dashboard aiops-worker
```

### Method 3: Docker Installation

#### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

#### Quick Docker Setup
```bash
# Clone repository
git clone https://github.com/your-org/aiops-system.git
cd aiops-system

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# Initialize system
docker-compose exec aiops-engine python manage.py init
```

#### Docker Production Setup
```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d

# Scale workers for high throughput
docker-compose -f docker-compose.prod.yml up -d --scale aiops-worker=3
```

### Method 4: Kubernetes Installation

#### Prerequisites
- Kubernetes 1.20+
- Helm 3.0+
- kubectl configured

#### Helm Installation
```bash
# Add AIOps Helm repository
helm repo add aiops https://charts.aiops.example.com
helm repo update

# Install with default values
helm install aiops aiops/aiops-platform

# Or with custom values
helm install aiops aiops/aiops-platform -f values.yaml
```

#### Manual Kubernetes Deployment
```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmaps/
kubectl apply -f k8s/secrets/
kubectl apply -f k8s/services/
kubectl apply -f k8s/deployments/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=aiops-engine -n aiops --timeout=300s
```

## Configuration

### Environment Variables (.env)
```bash
# Core Configuration
AIOPS_ENV=production
AIOPS_SECRET_KEY=your-secret-key-here
AIOPS_DEBUG=false

# Database Configuration
DATABASE_URL=postgresql://aiops:password@localhost:5432/aiops_db
REDIS_URL=redis://localhost:6379/0

# ML/AI Configuration
OPENAI_API_KEY=your-openai-api-key
ML_MODEL_PATH=/opt/aiops/models
ENABLE_PREDICTIONS=true

# Monitoring Configuration
PROMETHEUS_URL=http://localhost:9090
ELASTICSEARCH_URL=http://localhost:9200
GRAFANA_URL=http://localhost:3000

# Security Configuration
JWT_SECRET=your-jwt-secret
API_RATE_LIMIT=1000
ENABLE_CORS=true
ALLOWED_HOSTS=localhost,yourdomain.com

# Notification Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
EMAIL_SMTP_HOST=smtp.yourdomain.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=aiops@yourdomain.com
EMAIL_PASSWORD=your-email-password

# Performance Configuration
WORKER_CONCURRENCY=4
MAX_MEMORY_USAGE=8GB
CACHE_TTL=3600
```

### Main Configuration (config/aiops.conf)
```yaml
# AIOps Main Configuration

# System Settings
system:
  name: "AIOps Enterprise"
  version: "1.0.0"
  timezone: "UTC"
  log_level: "INFO"

# Machine Learning Configuration
ml:
  anomaly_detection:
    enabled: true
    model: "isolation_forest"
    contamination: 0.1
    retrain_interval: "24h"
  
  prediction:
    enabled: true
    horizon_days: 30
    confidence_threshold: 0.8
  
  alerting:
    correlation_threshold: 0.7
    noise_reduction: true
    auto_suppress: true

# Automation Configuration
automation:
  enabled: true
  approval_required: false
  max_actions_per_hour: 10
  cooldown_minutes: 15
  
  actions:
    restart_service: true
    scale_service: true
    clear_cache: true
    notify_team: true

# Monitoring Configuration
monitoring:
  interval_seconds: 30
  retention_days: 90
  metrics_buffer_size: 10000
  
  sources:
    prometheus: true
    elasticsearch: true
    custom_apis: true

# Security Configuration
security:
  authentication: "jwt"
  session_timeout: "24h"
  password_policy: "strong"
  audit_logging: true
  
  rbac:
    enabled: true
    default_role: "observer"
    admin_users: ["admin@yourdomain.com"]
```

## Post-Installation Setup

### 1. Verify Installation
```bash
# Check service status
systemctl status aiops-engine aiops-dashboard aiops-worker

# Test API connectivity
curl http://localhost:8000/api/health

# Test web interface
curl http://localhost:5000/health
```

### 2. Initialize Demo Data
```bash
# Generate sample data for testing
python demo_data_generator.py

# Run basic functionality test
python test_aiops.py
```

### 3. Configure Monitoring Sources
```bash
# Add Prometheus targets
python manage.py add-prometheus --url http://your-prometheus:9090

# Configure Elasticsearch
python manage.py add-elasticsearch --url http://your-elasticsearch:9200

# Test monitoring connections
python manage.py test-connections
```

### 4. Setup Notifications
```bash
# Configure Slack integration
python manage.py setup-slack --webhook-url "https://hooks.slack.com/..."

# Setup email notifications
python manage.py setup-email --smtp-host smtp.yourdomain.com

# Test notifications
python manage.py test-notifications
```

### 5. Create User Accounts
```bash
# Create admin user
python manage.py create-user --email admin@yourdomain.com --role admin

# Create team users
python manage.py create-user --email devops@yourdomain.com --role operator
python manage.py create-user --email sre@yourdomain.com --role analyst
```

## Service Management

### Systemd Services (Linux)

#### Start Services
```bash
sudo systemctl start aiops-engine
sudo systemctl start aiops-dashboard
sudo systemctl start aiops-worker
```

#### Stop Services
```bash
sudo systemctl stop aiops-engine
sudo systemctl stop aiops-dashboard
sudo systemctl stop aiops-worker
```

#### Restart Services
```bash
sudo systemctl restart aiops-engine
sudo systemctl restart aiops-dashboard
sudo systemctl restart aiops-worker
```

#### Check Status
```bash
sudo systemctl status aiops-engine
sudo journalctl -u aiops-engine -f  # Follow logs
```

### Process Management (Manual)

#### Start Services Manually
```bash
# In separate terminals or use screen/tmux
cd /opt/aiops

# Start ML engine
source venv/bin/activate
python -m aiops.engine &

# Start web dashboard
python -m aiops.dashboard &

# Start background worker
python -m aiops.worker &
```

## Troubleshooting

### Common Issues

#### 1. Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep :8000
netstat -tulpn | grep :5000

# Change ports in configuration
nano .env
# Modify AIOPS_API_PORT and AIOPS_WEB_PORT
```

#### 2. Database Connection Issues
```bash
# Test database connectivity
python -c "import psycopg2; psycopg2.connect('postgresql://aiops:password@localhost:5432/aiops_db')"

# Reset database
python manage.py reset-db
python manage.py migrate
```

#### 3. Permission Issues
```bash
# Fix file permissions
sudo chown -R aiops:aiops /opt/aiops
chmod +x /opt/aiops/scripts/*
```

#### 4. Memory Issues
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Adjust worker memory limits
export WORKER_MEMORY_LIMIT=2GB
```

### Log Locations
- **System logs**: `/var/log/aiops/`
- **Application logs**: `/opt/aiops/logs/`
- **Service logs**: `journalctl -u aiops-*`
- **Docker logs**: `docker logs aiops-engine`

### Getting Help
- **Documentation**: https://docs.aiops.example.com
- **Community Forum**: https://community.aiops.example.com
- **GitHub Issues**: https://github.com/your-org/aiops-system/issues
- **Enterprise Support**: support@aiops.example.com

## Security Considerations

### Initial Security Setup
```bash
# Generate secure secrets
python manage.py generate-secrets

# Setup SSL/TLS certificates
python manage.py setup-ssl --domain yourdomain.com

# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Production Security Checklist
- [ ] Change default passwords
- [ ] Enable SSL/TLS encryption
- [ ] Configure firewall rules
- [ ] Setup audit logging
- [ ] Enable authentication
- [ ] Configure RBAC permissions
- [ ] Setup backup procedures
- [ ] Enable monitoring alerts
- [ ] Review security policies
- [ ] Schedule security updates

## Backup and Recovery

### Database Backup
```bash
# Create backup
pg_dump aiops_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated backup script
crontab -e
# Add: 0 2 * * * /opt/aiops/scripts/backup.sh
```

### Configuration Backup
```bash
# Backup configuration files
tar -czf aiops-config-$(date +%Y%m%d).tar.gz \
    /opt/aiops/config/ \
    /opt/aiops/.env \
    /etc/systemd/system/aiops-*.service
```

### Disaster Recovery
```bash
# Restore from backup
psql aiops_db < backup_20240101_020000.sql

# Restore configuration
tar -xzf aiops-config-20240101.tar.gz -C /
systemctl daemon-reload
systemctl restart aiops-*
```