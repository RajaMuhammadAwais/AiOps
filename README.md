# AIOps - Autonomous Incident Management System

An intelligent incident management platform that combines machine learning, natural language processing, and automation to monitor, analyze, and respond to system anomalies in real-time.

## Features

### 🤖 AI-Powered Analysis
- **Anomaly Detection**: ML-based detection using Isolation Forest and Prophet forecasting
- **Alert Correlation**: Intelligent grouping and noise reduction of related alerts
- **Root Cause Analysis**: LLM-powered explanations of incidents and recommended actions
- **Pattern Recognition**: Learning from historical incidents to improve predictions

### 🔧 Self-Healing Capabilities
- **Automated Actions**: Restart services, scale deployments, clear caches
- **Rule Engine**: Configurable conditions for triggering self-healing actions
- **Cooldown Management**: Prevent action spam with intelligent timing controls
- **Action History**: Track all automated interventions with success rates

### 💬 ChatOps Integration
- **Natural Language Queries**: Ask about system status, incidents, and metrics
- **Alert Rule Creation**: Convert plain English to monitoring rules
- **Runbook Generation**: AI-generated troubleshooting guides
- **Interactive CLI**: Rich terminal interface for operations

### 📊 System Monitoring
- **Comprehensive Metrics**: CPU, memory, disk, network, and process monitoring
- **Multi-Source Data**: Support for Prometheus, system metrics, and custom sources
- **Health Scoring**: Intelligent system health assessment
- **Historical Analysis**: Trend analysis and baseline learning

## Quick Start

### Prerequisites
- Python 3.11+
- Required packages (automatically installed)

### Installation

```bash
# Clone or download the project
cd aiops-system

# Install dependencies (already configured)
# Dependencies include: scikit-learn, pandas, openai, click, rich, etc.
```

### Basic Usage

#### 1. Initialize the System
```bash
python aiops_main.py init
```

#### 2. Generate Demo Data
```bash
python demo_data_generator.py
```

#### 3. Check System Status
```bash
python aiops_main.py status
```

#### 4. Start Real-time Monitoring
```bash
python aiops_main.py monitor
```

#### 5. Query the AI Assistant
```bash
python aiops_main.py ask "What's the current system health?"
python aiops_main.py ask "Show me critical incidents from the last hour"
```

#### 6. View Current Metrics
```bash
python aiops_main.py metrics --cpu --memory
```

#### 7. List Recent Incidents
```bash
python aiops_main.py incidents
```

## Architecture

### Core Components

1. **ML Engine** (`src/ml/`)
   - `anomaly_detector.py`: Isolation Forest + Prophet forecasting
   - `alert_correlator.py`: TF-IDF similarity and DBSCAN clustering

2. **Monitoring** (`src/monitoring/`)
   - `system_monitor.py`: Multi-source metrics collection

3. **Alerting** (`src/alerting/`)
   - `alert_manager.py`: Self-healing actions and alert processing

4. **ChatOps** (`src/chatops/`)
   - `llm_assistant.py`: OpenAI-powered incident analysis

5. **CLI Interface** (`src/cli/`)
   - `aiops_cli.py`: Rich terminal interface

### Data Models

- **Incident**: Core incident with AI analysis fields
- **Alert**: Individual alerts with correlation metadata  
- **Metric**: Time-series data points with labels
- **SelfHealingAction**: Automated response definitions

## AI Features

### Anomaly Detection
- **Isolation Forest**: Detects outliers in multi-dimensional metric space
- **Prophet Forecasting**: Time-series anomaly detection with seasonality
- **Clustering**: Groups related anomalies for incident creation

### Alert Intelligence
- **Correlation**: Groups similar alerts using text similarity
- **Noise Reduction**: Suppresses repetitive low-value alerts
- **Severity Prediction**: ML-based incident severity classification

### LLM Integration
- **Incident Explanation**: Plain-English analysis of technical issues
- **Root Cause Analysis**: AI-powered investigation and recommendations
- **Natural Language Queries**: Conversational system interaction
- **Runbook Generation**: Automated troubleshooting procedures

## Self-Healing Actions

### Default Actions
1. **Service Restart**: Restart services on high resource usage
2. **Cache Clearing**: Clear caches on memory pressure
3. **Auto-scaling**: Scale services on high load
4. **Team Alerting**: Escalate critical incidents

### Custom Actions
```python
from alerting.alert_manager import SelfHealingAction, ActionType

custom_action = SelfHealingAction(
    id="custom_restart",
    name="Custom Service Restart",
    action_type=ActionType.RESTART_SERVICE,
    condition="cpu_usage > 95 AND duration > 600",
    parameters={"service_patterns": ["my-service"]},
    cooldown_minutes=20
)
```

## Configuration

### Environment Variables
```bash
# Required for AI features
export OPENAI_API_KEY="your-openai-api-key"

# Optional: Prometheus integration
export PROMETHEUS_URL="http://localhost:9090"
```

### Monitoring Configuration
- **Metrics Interval**: 30 seconds (configurable)
- **History Retention**: 1000 samples (configurable)
- **Anomaly Threshold**: Auto-calibrated based on data

## Examples

### Scenario 1: High CPU Detection
```bash
# System detects CPU spike
# → Anomaly detector flags unusual CPU pattern
# → Alert correlator groups related CPU alerts
# → LLM explains: "High CPU usage detected on web-server. Likely caused by traffic spike or resource leak."
# → Self-healing action: Restart service after 5 minutes if persistent
# → Incident created with AI recommendations
```

### Scenario 2: Memory Leak Detection
```bash
# Gradual memory increase detected
# → Prophet model identifies trend deviation
# → Alert created: "Memory usage trending upward"
# → LLM analysis: "Gradual memory leak detected. Recommend restart and code review."
# → Cache clearing attempted first, then service restart
```

### Scenario 3: Alert Storm Management
```bash
# Multiple related alerts received
# → Alert correlator groups similar alerts
# → Noise reduction suppresses duplicates
# → Single incident created instead of alert spam
# → Team receives one consolidated notification
```

## API Integration

### Prometheus Integration
```python
# Automatic metrics collection from Prometheus
monitor = SystemMonitor(prometheus_url="http://localhost:9090")
metrics = await monitor.collect_metrics()
```

### Custom Metrics
```python
# Add custom metric sources
def custom_metrics_collector():
    return [
        {
            'name': 'custom_metric',
            'value': 42.0,
            'timestamp': datetime.now(),
            'source': 'custom',
            'labels': {'service': 'my-app'}
        }
    ]
```

## Advanced Usage

### Training Custom Models
```python
# Train anomaly detector with your data
detector = AnomalyDetector()
detector.train_baseline(historical_metrics)
```

### Custom Alert Rules
```bash
# Natural language rule creation
python aiops_main.py ask "Create alert rule: notify me when API response time exceeds 2 seconds for 5 minutes"
```

### Batch Analysis
```python
# Analyze historical incidents
incidents = load_historical_incidents()
patterns = await llm_assistant.analyze_alert_pattern(incidents)
```

## Monitoring Dashboard (Future)

The system is designed to support a web dashboard with:
- Real-time metrics visualization
- Incident timeline and correlation graphs  
- Alert pattern analysis
- Self-healing action effectiveness
- System health scoring trends

## Contributing

### Adding New Components
1. Create new modules in appropriate `src/` subdirectories
2. Follow existing patterns for error handling and logging
3. Add comprehensive docstrings and type hints
4. Update CLI interface as needed

### Extending ML Capabilities
- Add new anomaly detection algorithms in `ml/`
- Implement custom correlation strategies
- Enhance prediction models with domain knowledge

## Troubleshooting

### Common Issues
1. **"OpenAI client not initialized"**: Set OPENAI_API_KEY environment variable
2. **"No historical data"**: Run demo data generator first
3. **Permission errors**: Ensure proper file system permissions
4. **Import errors**: Check Python path and package installation

### Debug Mode
```bash
# Enable debug logging
export AIOPS_DEBUG=1
python aiops_main.py monitor
```

## License

This project demonstrates core AIOps concepts and is designed for educational and prototyping purposes.