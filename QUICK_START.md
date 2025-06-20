# AIOps Quick Start Guide

Get your AIOps system running in minutes with our automated installer.

## One-Line Installation

```bash
curl -fsSL https://raw.githubusercontent.com/aiops-platform/aiops-system/main/install_aiops.sh | bash
```

## Manual Installation Steps

### 1. Download the Installer
```bash
wget https://raw.githubusercontent.com/aiops-platform/aiops-system/main/install_aiops.sh
chmod +x install_aiops.sh
```

### 2. Run Installation
```bash
# Basic installation
./install_aiops.sh

# Custom installation directory
./install_aiops.sh --install-dir /home/myuser/aiops

# Non-interactive mode
./install_aiops.sh --non-interactive

# Skip demo data
./install_aiops.sh --no-demo-data

# Enable firewall configuration
./install_aiops.sh --configure-firewall
```

### 3. Start AIOps
```bash
# Using startup script
/opt/aiops/scripts/start_aiops.sh

# Using systemd (Linux)
sudo systemctl start aiops-engine aiops-dashboard

# Manual start
cd /opt/aiops
source venv/bin/activate
python test_aiops.py
```

## First Run Demo

### Run the Core Demo
```bash
cd /opt/aiops
source venv/bin/activate
python test_aiops.py
```

**Expected Output:**
- System health monitoring
- ML anomaly detection (6 anomalies detected)
- Alert correlation (25% noise reduction)
- Self-healing actions (3 actions executed)

### View Enhancement Capabilities
```bash
python high_level_aiops_enhancements.py
```

**Expected Output:**
- Enhancement capability matrix
- Predictive analytics features
- Intelligent automation roadmap
- Implementation timeline

### Start Web Dashboard
```bash
python web_dashboard.py
```

**Access Points:**
- Web Interface: http://localhost:5000
- API Endpoints: http://localhost:8000

## Configuration

### Set OpenAI API Key (Optional)
```bash
nano /opt/aiops/.env
# Add: OPENAI_API_KEY=sk-your-key-here
```

### Configure Monitoring Sources
```bash
# Edit environment file
nano /opt/aiops/.env

# Add your Prometheus URL
PROMETHEUS_URL=http://your-prometheus:9090

# Add your Elasticsearch URL  
ELASTICSEARCH_URL=http://your-elasticsearch:9200
```

## Verification Commands

### Check Installation
```bash
# Verify services
systemctl status aiops-engine aiops-dashboard

# Test API connectivity
curl http://localhost:8000/api/health

# Check web interface
curl http://localhost:5000/health
```

### View Logs
```bash
# Application logs
tail -f /opt/aiops/logs/*.log

# System service logs
journalctl -u aiops-engine -f
journalctl -u aiops-dashboard -f
```

## Common Usage Patterns

### Monitor System Health
```bash
cd /opt/aiops && source venv/bin/activate

# View current status
python -c "
from src.monitoring.system_monitor import SystemMonitor
monitor = SystemMonitor()
status = monitor.get_current_status()
print(f'Health Score: {status[\"health_score\"]}/100')
print(f'CPU: {status[\"cpu_usage\"]:.1f}%')
print(f'Memory: {status[\"memory_usage\"]:.1f}%')
"
```

### Generate Fresh Demo Data
```bash
cd /opt/aiops && source venv/bin/activate
python demo_data_generator.py
```

### Run Specific Components
```bash
cd /opt/aiops && source venv/bin/activate

# ML anomaly detection only
python -c "
import asyncio
from src.ml.anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
print('Anomaly detector ready')
"

# Alert correlation only
python -c "
from src.ml.alert_correlator import AlertCorrelator
correlator = AlertCorrelator()
print('Alert correlator ready')
"
```

## Integration Examples

### Add Custom Metrics
```bash
cd /opt/aiops && source venv/bin/activate
python -c "
from src.monitoring.system_monitor import SystemMonitor
import json
from datetime import datetime

monitor = SystemMonitor()
custom_metrics = [
    {
        'name': 'custom_app_response_time',
        'value': 150.5,
        'timestamp': datetime.now(),
        'source': 'my_app',
        'labels': {'environment': 'production'}
    }
]

# Process custom metrics
print('Custom metrics added')
"
```

### Create Custom Alerts
```bash
cd /opt/aiops && source venv/bin/activate
python -c "
from src.models.incident import Alert, AlertSource, IncidentSeverity
from datetime import datetime

alert = Alert(
    id='custom_alert_001',
    name='High Response Time',
    severity=IncidentSeverity.HIGH,
    source=AlertSource.CUSTOM,
    timestamp=datetime.now(),
    message='Application response time exceeded threshold',
    labels={'service': 'web-app', 'environment': 'prod'}
)

print(f'Created alert: {alert.name} ({alert.severity.value})')
"
```

## Troubleshooting

### Installation Issues
```bash
# Check system requirements
free -h  # Memory check
df -h    # Disk space check
python3.11 --version  # Python version

# Check dependencies
systemctl status postgresql redis

# View installation logs
tail -f /var/log/aiops/install.log
```

### Runtime Issues
```bash
# Check process status
ps aux | grep python | grep aiops

# Check port usage
netstat -tulpn | grep :5000
netstat -tulpn | grep :8000

# Check file permissions
ls -la /opt/aiops/
ls -la /opt/aiops/scripts/
```

### Performance Issues
```bash
# Monitor resource usage
htop
iotop
nethogs

# Check Python process memory
ps aux --sort=-%mem | grep python

# Review configuration
cat /opt/aiops/.env | grep -E "(MEMORY|WORKER|CACHE)"
```

## Service Management

### Systemd Commands (Linux)
```bash
# Start services
sudo systemctl start aiops-engine aiops-dashboard

# Stop services
sudo systemctl stop aiops-engine aiops-dashboard

# Restart services
sudo systemctl restart aiops-engine aiops-dashboard

# Enable auto-start
sudo systemctl enable aiops-engine aiops-dashboard

# Check status
sudo systemctl status aiops-engine
sudo systemctl status aiops-dashboard

# View logs
sudo journalctl -u aiops-engine -f
sudo journalctl -u aiops-dashboard -f
```

### Manual Service Management
```bash
# Start manually
cd /opt/aiops
./scripts/start_aiops.sh

# Stop manually
./scripts/stop_aiops.sh

# Check if running
pgrep -f "python.*aiops"
```

## Updating AIOps

### Update from Git
```bash
cd /opt/aiops
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart aiops-engine aiops-dashboard
```

### Backup Before Update
```bash
# Backup configuration
sudo tar -czf aiops-backup-$(date +%Y%m%d).tar.gz \
    /opt/aiops/.env \
    /opt/aiops/config/ \
    /opt/aiops/data/ \
    /etc/systemd/system/aiops-*.service

# Backup database
sudo -u postgres pg_dump aiops_db > aiops-db-backup-$(date +%Y%m%d).sql
```

## Uninstallation

### Remove AIOps
```bash
# Stop services
sudo systemctl stop aiops-engine aiops-dashboard
sudo systemctl disable aiops-engine aiops-dashboard

# Remove systemd files
sudo rm /etc/systemd/system/aiops-*.service
sudo systemctl daemon-reload

# Remove installation
sudo rm -rf /opt/aiops
sudo rm -rf /var/log/aiops
sudo rm -rf /etc/aiops

# Remove user (optional)
sudo userdel -r aiops

# Remove database (optional)
sudo -u postgres dropdb aiops_db
sudo -u postgres dropuser aiops
```

## Next Steps

1. **Read the Features Guide**: `FEATURES_GUIDE.md`
2. **Review Installation Guide**: `INSTALLATION_GUIDE.md`
3. **Check Deployment Options**: `DEPLOYMENT_GUIDE.md`
4. **Configure Monitoring Sources**: Add Prometheus/Elasticsearch endpoints
5. **Set Up Notifications**: Configure Slack/email alerts
6. **Enable AI Features**: Add OpenAI API key for advanced analysis

## Support Resources

- **Documentation**: All guides available in the installation directory
- **Demo Scripts**: `test_aiops.py`, `high_level_aiops_enhancements.py`
- **Configuration**: `.env` file for all settings
- **Logs**: `/opt/aiops/logs/` for troubleshooting
- **Community**: GitHub issues for questions and bug reports

## Performance Optimization

### For Production Use
```bash
# Increase worker processes
echo "WORKER_CONCURRENCY=8" >> /opt/aiops/.env

# Optimize memory usage
echo "MAX_MEMORY_USAGE=8GB" >> /opt/aiops/.env

# Enable advanced caching
echo "CACHE_TTL=7200" >> /opt/aiops/.env

# Restart to apply changes
sudo systemctl restart aiops-engine aiops-dashboard
```

### For High-Volume Environments
```bash
# Scale with multiple workers
sudo systemctl stop aiops-engine
sudo cp /etc/systemd/system/aiops-engine.service /etc/systemd/system/aiops-engine@.service
sudo systemctl daemon-reload
sudo systemctl start aiops-engine@1 aiops-engine@2 aiops-engine@3
```

Your AIOps system is now ready for intelligent incident management!