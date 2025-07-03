# AIOps Dashboard: Intelligent Incident Management & Monitoring

## Overview
AIOps Dashboard is a modern, full-stack platform for autonomous incident management, real-time monitoring, and intelligent operations. It combines advanced ML/AI analytics, alert/incident management, actionable recommendations, and a rich web dashboard for SREs, DevOps, and IT teams.

---

## Features
- **Real-Time System Health & Metrics**: CPU, memory, disk, and network monitoring with live updates.
- **Incident & Alert Management**: Grouped incidents, severity filtering, lifecycle modal, and alert suppression/muting.
- **ML/AI Insights**: Anomaly detection, predictive analytics, root cause analysis, and automated recommendations.
- **Self-Healing Automation**: Tracks actions executed, success rates, and active rules with timeline visualization.
- **Performance Metrics**: Response time, error rate, throughput, and historical trends.
- **Customizable Thresholds**: Set and save alerting thresholds for key metrics.
- **Interactive Web Dashboard**: Responsive UI with Chart.js visualizations and AI assistant query interface.
- **API-First Backend**: RESTful endpoints for all dashboard features, ready for integration and automation.
- **CI/CD & Code Quality**: GitHub Actions workflow, PEP8/flake8 compliance, and comprehensive tests.

---

## Quick Start

### 1. Install Requirements
```bash
pip install -r requirements.txt
```

### 2. Run the Backend (Flask)
```bash
python3 web_dashboard.py
```

### 3. Open the Dashboard
Visit [http://localhost:5000](http://localhost:5000) in your browser.

---

## Project Structure
```
aiops_main.py
web_dashboard.py           # Flask backend (API + dashboard)
templates/dashboard.html  # Main dashboard UI (HTML/JS/CSS)
src/
  alerting/               # Alert manager logic
  automation/             # Self-healing/orchestration
  chatops/                # LLM assistant
  cli/                    # CLI tools
  deployment/             # Orchestrator
  intelligence/           # ML/AI predictive engine
  ml/                     # Analytics, anomaly detection
  models/                 # Data models
  monitoring/             # System/log monitoring
  observability/          # Tracing
requirements.txt
README.md
LICENSE.md
.github/workflows/ci-cd.yaml
```

---

## API Endpoints
- `/api/status` — System health & metrics
- `/api/incidents` — List active incidents
- `/api/alerts` — List recent alerts
- `/api/self-healing` — Self-healing summary
- `/api/health-heatmap` — Health heatmap data
- `/api/historical-trends` — Historical metric trends
- `/api/anomaly-timeline` — Anomaly/action timeline
- `/api/log-events` — Recent log events
- `/api/ai-recommendations` — Automated recommendations
- `/api/rca-insights` — Root cause analysis insights
- `/api/grouped-incidents` — Grouped incidents & RCA
- `/api/ml-insights` — ML anomaly/forecast/classification
- `/api/performance-metrics` — Performance metrics & trends
- `/api/self-healing-timeline` — Self-healing timeline data
- `/api/set-thresholds` — Set alerting thresholds
- `/api/suppress-alert` — Suppress/mute alert
- `/api/query` — AI assistant query

---

## Testing
Run all API and backend tests:
```bash
python3 test_api_endpoints.py
pytest
```

---

## Contributing
See `CONTRIBUTING` for guidelines. PRs, issues, and feature requests are welcome!

---

## License
See `LICENSE.md` for details.

---

## Authors & Credits
- Project lead: Your Name
- Contributors: See GitHub history

---

## Notes
- For advanced ML/AI features, see `src/intelligence/predictive_engine.py` and `src/ml/`.
- For custom integrations, extend the REST API or add new dashboard cards.
- For deployment, see `DEPLOYMENT_GUIDE.md`.
