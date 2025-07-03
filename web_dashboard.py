#!/usr/bin/env python3
"""
AIOps Web Dashboard - Visual Incident Management Interface
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import asyncio
import sys
import os
from datetime import datetime, timedelta
import threading
import time
from src.intelligence.predictive_engine import PredictiveIntelligenceEngine

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

app = Flask(__name__)
CORS(app)

# Global data store for the dashboard
dashboard_data = {
    'system_status': {},
    'incidents': [],
    'alerts': [],
    'metrics': [],
    'anomalies': [],
    'self_healing_stats': {},
    'log_events': [],  # Add log events for real-time log monitoring
    'last_updated': datetime.now()
}

predictive_engine = PredictiveIntelligenceEngine()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """Get current system status"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'health_score': 85,
        'cpu_usage': 45.2,
        'memory_usage': 67.8,
        'disk_usage': 72.1,
        'active_incidents': len([i for i in dashboard_data['incidents'] if i.get('status') == 'open']),
        'total_alerts': len(dashboard_data['alerts']),
        'last_updated': dashboard_data['last_updated'].isoformat()
    })

@app.route('/api/incidents')
def api_incidents():
    """Get recent incidents"""
    return jsonify({
        'incidents': dashboard_data['incidents'][-20:],  # Last 20 incidents
        'total': len(dashboard_data['incidents'])
    })

@app.route('/api/alerts')
def api_alerts():
    """Get recent alerts"""
    return jsonify({
        'alerts': dashboard_data['alerts'][-50:],  # Last 50 alerts
        'total': len(dashboard_data['alerts'])
    })

@app.route('/api/metrics')
def api_metrics():
    """Get current metrics"""
    return jsonify({
        'metrics': dashboard_data['metrics'][-100:],  # Last 100 metrics
        'anomalies': dashboard_data['anomalies'][-20:]  # Last 20 anomalies
    })

@app.route('/api/self-healing')
def api_self_healing():
    """Get self-healing statistics"""
    return jsonify(dashboard_data['self_healing_stats'])

@app.route('/api/query', methods=['POST'])
def api_query():
    """Process natural language queries"""
    data = request.get_json()
    query = data.get('query', '')
    
    # Simple query processing (in production, would use LLM)
    response = process_query(query)
    
    return jsonify({
        'query': query,
        'response': response,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/log-events')
def api_log_events():
    """Get recent log events (errors, critical)"""
    return jsonify({
        'log_events': dashboard_data['log_events'][-20:],  # Last 20 log events
        'total': len(dashboard_data['log_events'])
    })

@app.route('/api/health-heatmap')
def api_health_heatmap():
    """Get real-time status for heatmap (CPU, Memory, Disk, Network, etc.)"""
    # Demo data; in production, fetch from monitoring source
    return jsonify({
        'components': [
            {'name': 'CPU', 'usage': 45.2, 'status': 'healthy'},
            {'name': 'Memory', 'usage': 67.8, 'status': 'warning'},
            {'name': 'Disk', 'usage': 72.1, 'status': 'critical'},
            {'name': 'Network', 'usage': 38.5, 'status': 'healthy'}
        ],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/historical-trends')
def api_historical_trends():
    """Get historical trends for system metrics (last 24h, demo)"""
    # Demo data: 7 time points
    return jsonify({
        'labels': ['10:00', '10:05', '10:10', '10:15', '10:20', '10:25', '10:30'],
        'cpu': [40, 42, 45, 47, 44, 46, 45],
        'memory': [60, 62, 65, 67, 66, 68, 67],
        'disk': [70, 71, 72, 73, 72, 74, 73],
        'network': [35, 36, 38, 37, 39, 40, 38]
    })

@app.route('/api/anomaly-timeline')
def api_anomaly_timeline():
    """Get anomaly and action events for timeline visualization"""
    # Demo data
    return jsonify({
        'anomalies': [
            {'time': '10:05', 'type': 'anomaly', 'desc': 'CPU spike', 'severity': 'high'},
            {'time': '10:18', 'type': 'anomaly', 'desc': 'Response time anomaly', 'severity': 'medium'},
            {'time': '10:22', 'type': 'anomaly', 'desc': 'Disk IO anomaly', 'severity': 'high'}
        ],
        'actions': [
            {'time': '10:06', 'type': 'action', 'desc': 'Restarted nginx', 'result': 'success'},
            {'time': '10:19', 'type': 'action', 'desc': 'Scaled up workers', 'result': 'success'}
        ]
    })

@app.route('/api/ai-recommendations')
def api_ai_recommendations():
    """AI-driven recommendations based on health score and alerts (demo logic)"""
    # Example: Use health score and alerts to generate recommendations
    health =  dashboard_data.get('system_status', {}).get('health_score', 85) or 85
    alerts = dashboard_data.get('alerts', [])
    recs = []
    if health < 70:
        recs.append("System health is low. Consider scaling up resources or investigating high-load services.")
    elif health < 90:
        recs.append("System health is moderate. Monitor CPU and memory usage closely.")
    else:
        recs.append("System is healthy. Continue regular monitoring.")
    # Alert-based recs
    for alert in alerts[-3:]:
        if 'cpu' in alert['message'].lower():
            recs.append(f"Optimize {alert['labels'].get('service','a service')} configuration to reduce CPU usage.")
        if 'disk' in alert['message'].lower():
            recs.append("Consider cleaning up disk space or expanding storage.")
        if 'network' in alert['message'].lower():
            recs.append("Investigate network connectivity issues in affected regions.")
    if not recs:
        recs.append("No immediate recommendations. All systems nominal.")
    return jsonify({'recommendations': recs})

@app.route('/api/rca-insights')
def api_rca_insights():
    """Root Cause Analysis insights (demo logic)"""
    # Example: Analyze recent incidents/alerts for patterns
    insights = []
    recent_alerts = dashboard_data.get('alerts', [])[-5:]
    for alert in recent_alerts:
        if 'cpu' in alert['message'].lower():
            insights.append(f"Frequent high CPU usage detected in {alert['labels'].get('service','a service')}. Consider scaling or optimizing workload.")
        if 'disk' in alert['message'].lower():
            insights.append(f"Disk space issues in {alert['labels'].get('service','a service')}. Clean up unused files or expand storage.")
        if 'timeout' in alert['message'].lower():
            insights.append(f"Timeouts observed for {alert['labels'].get('service','a service')}. Check service dependencies and network latency.")
    if not insights:
        insights.append("No root cause patterns detected in recent incidents.")
    return jsonify({'insights': insights})

@app.route('/api/suppress-alert', methods=['POST'])
def api_suppress_alert():
    """Suppress/mute an alert for a given period (demo logic)"""
    data = request.get_json()
    alert_id = data.get('alert_id')
    duration = data.get('duration', 10)  # minutes
    # In production, store suppression in DB or memory
    if not hasattr(dashboard_data, 'suppressed_alerts'):
        dashboard_data['suppressed_alerts'] = {}
    dashboard_data['suppressed_alerts'][alert_id] = time.time() + duration * 60
    return jsonify({'status': 'suppressed', 'alert_id': alert_id, 'until': dashboard_data['suppressed_alerts'][alert_id]})

@app.route('/api/grouped-incidents')
def api_grouped_incidents():
    """Group related incidents and provide root cause suggestions (real-time)"""
    # Group by affected service, use ML/AI for RCA if available
    groups = {}
    for inc in dashboard_data['incidents']:
        key = ','.join(inc.get('affected_services', []))
        if key not in groups:
            groups[key] = []
        groups[key].append(inc)
    grouped = []
    for service, incs in groups.items():
        # Use ML/AI for RCA suggestion if available
        rca_suggestion = None
        if hasattr(predictive_engine, 'explain_root_cause'):
            try:
                rca_suggestion = predictive_engine.explain_root_cause(incs)
            except Exception:
                rca_suggestion = None
        if not rca_suggestion:
            # Fallback: simple heuristics
            if any('cpu' in (i.get('description','').lower()) for i in incs):
                rca_suggestion = f"High CPU usage in {service}. Possible resource contention or traffic spike."
            elif any('disk' in (i.get('description','').lower()) for i in incs):
                rca_suggestion = f"Disk issues in {service}. Check storage and IO."
            elif any('timeout' in (i.get('description','').lower()) for i in incs):
                rca_suggestion = f"Timeouts in {service}. Check dependencies and network."
        grouped.append({
            'service': service,
            'incidents': incs,
            'rca_suggestion': rca_suggestion,
            'severity': max((i.get('severity','low') for i in incs), key=lambda s: ['low','medium','high','critical'].index(s) if s in ['low','medium','high','critical'] else 0),
            'count': len(incs),
            'title': f"{service} ({len(incs)} incidents)",
            'status': ', '.join(set(i.get('status','N/A') for i in incs)),
            'description': '; '.join(i.get('description','') for i in incs if i.get('description'))
        })
    return jsonify({'groups': grouped})

@app.route('/api/ml-insights')
def api_ml_insights():
    """Return ML insights: anomaly trend, forecast, and classification (real-time)"""
    # Use real metrics/anomalies from dashboard_data
    metrics = dashboard_data.get('metrics', [])
    anomalies = dashboard_data.get('anomalies', [])
    # Train or update models if needed (could be cached in production)
    if metrics:
        predictive_engine.train_capacity_models(metrics, horizon_days=2)
    # Trend: use anomaly timestamps
    trend_labels = []
    trend_counts = []
    if anomalies:
        # Group anomalies by hour
        from collections import Counter
        from datetime import datetime
        hours = [datetime.fromisoformat(a['timestamp']).strftime('%H:%M') for a in anomalies]
        counter = Counter(hours)
        trend_labels = sorted(counter.keys())
        trend_counts = [counter[k] for k in trend_labels]
    else:
        trend_labels = []
        trend_counts = []
    # Forecast: use model output if available
    forecast = "No forecast available."
    if predictive_engine.capacity_models.get('cpu_usage'):
        breach = predictive_engine.capacity_models['cpu_usage']['threshold_breach']
        if breach['will_breach']:
            forecast = f"CPU usage predicted to breach {breach['threshold']}% at {breach['breach_timestamp']}"
        else:
            forecast = breach.get('message', forecast)
    # Classification: group anomalies by category
    classification = []
    if anomalies:
        cat_counter = Counter([a.get('category','Other') for a in anomalies])
        classification = [{'category': k, 'count': v} for k, v in cat_counter.items()]
    total = sum(c['count'] for c in classification) if classification else 0
    prediction_accuracy = predictive_engine.capacity_models.get('cpu_usage',{}).get('forecast_accuracy', 90.0)
    return jsonify({
        'trend': {'labels': trend_labels, 'counts': trend_counts},
        'forecast': forecast,
        'classification': classification,
        'total': total,
        'prediction_accuracy': prediction_accuracy
    })

@app.route('/api/performance-metrics')
def api_performance_metrics():
    """Return real-time and historical performance metrics for dashboard charts."""
    # Simulate or use real data from dashboard_data['metrics']
    import random
    from datetime import datetime, timedelta
    metrics = dashboard_data.get('metrics', [])
    # Generate time labels for the last 12 intervals (e.g., 5-min or 1-hour)
    now = datetime.now()
    labels = [(now - timedelta(minutes=5*i)).strftime('%H:%M') for i in reversed(range(12))]
    # Aggregate or simulate data
    def get_metric_series(name):
        # Try to get real data, else simulate
        series = [m['value'] for m in metrics if m['name'] == name]
        if len(series) >= 12:
            return series[-12:]
        else:
            return [random.uniform(100, 300) if name=='response_time' else random.uniform(0, 1) if name=='error_rate' else random.uniform(1000, 2000) for _ in range(12)]
    response_time = get_metric_series('response_time')
    error_rate = get_metric_series('error_rate')
    throughput = get_metric_series('throughput')
    # Current values
    current = {
        'response_time': round(response_time[-1], 1),
        'error_rate': round(error_rate[-1], 3),
        'throughput': int(throughput[-1])
    }
    history = {
        'labels': labels,
        'response_time': [round(x,1) for x in response_time],
        'error_rate': [round(x,3) for x in error_rate],
        'throughput': [int(x) for x in throughput]
    }
    return jsonify({'current': current, 'history': history})

@app.route('/api/self-healing-timeline')
def api_self_healing_timeline():
    """Return timeline of self-healing actions and success rates."""
    import random
    from datetime import datetime, timedelta
    actions = dashboard_data.get('self_healing_actions', [])
    # Simulate last 10 intervals
    now = datetime.now()
    labels = [(now - timedelta(minutes=10*i)).strftime('%H:%M') for i in reversed(range(10))]
    actions_executed = [random.randint(1, 5) for _ in range(10)]
    success_rate = [round(random.uniform(70, 100), 1) for _ in range(10)]
    # Recent actions drilldown
    recent = actions[-5:] if actions else [
        {'time': (now-timedelta(minutes=i*3)).strftime('%H:%M'), 'action': f'Action {i+1}', 'success': bool(random.getrandbits(1))} for i in range(5)
    ]
    return jsonify({'labels': labels, 'actions': actions_executed, 'success_rate': success_rate, 'recent': recent})

@app.route('/api/set-thresholds', methods=['POST'])
def api_set_thresholds():
    """Set custom thresholds for CPU, memory, disk usage."""
    data = request.get_json()
    cpu = float(data.get('cpu', 85))
    mem = float(data.get('mem', 90))
    disk = float(data.get('disk', 95))
    dashboard_data['thresholds'] = {'cpu': cpu, 'mem': mem, 'disk': disk}
    return jsonify({'status': f'Thresholds updated: CPU={cpu}%, Memory={mem}%, Disk={disk}%'})

def process_query(query):
    """Process natural language query"""
    query_lower = query.lower()
    
    if 'status' in query_lower or 'health' in query_lower:
        return f"System health score: 85/100. CPU: 45.2%, Memory: 67.8%, Disk: 72.1%. {len(dashboard_data['incidents'])} total incidents."
    
    elif 'incident' in query_lower:
        open_incidents = [i for i in dashboard_data['incidents'] if i.get('status') == 'open']
        return f"Found {len(open_incidents)} open incidents. Most recent: {open_incidents[-1]['title'] if open_incidents else 'None'}"
    
    elif 'alert' in query_lower:
        recent_alerts = dashboard_data['alerts'][-5:]
        return f"Last 5 alerts: {', '.join([a.get('name', 'Unknown') for a in recent_alerts])}"
    
    elif 'anomal' in query_lower:
        return f"Detected {len(dashboard_data['anomalies'])} anomalies in the last monitoring cycle."
    
    else:
        return "I can help you with system status, incidents, alerts, and anomalies. Try asking about current system health or recent incidents."

def load_demo_data():
    """Load demo data into dashboard"""
    try:
        # Load incidents
        with open('demo_alerts.json', 'r') as f:
            alerts = json.load(f)
            dashboard_data['alerts'] = alerts
        
        # Create sample incidents from alerts
        incidents = []
        for i, alert in enumerate(alerts[:3]):  # Convert first 3 alerts to incidents
            incident = {
                'id': f'incident_{i}',
                'title': f"System Issue: {alert['name']}",
                'description': alert['message'],
                'severity': alert['severity'],
                'status': 'open' if i < 2 else 'resolved',
                'created_at': alert['timestamp'],
                'updated_at': alert['timestamp'],
                'affected_services': [alert.get('labels', {}).get('service', 'unknown')],
                'llm_explanation': 'AI analysis indicates resource contention issue requiring attention.',
                'predicted_resolution_time': 30
            }
            incidents.append(incident)
        
        dashboard_data['incidents'] = incidents
        
        # Load metrics
        with open('demo_current_data.json', 'r') as f:
            metrics = json.load(f)
            dashboard_data['metrics'] = metrics
        
        # Create sample anomalies
        dashboard_data['anomalies'] = [
            {
                'type': 'isolation_forest',
                'metric_name': 'cpu_usage',
                'anomaly_score': -0.65,
                'timestamp': datetime.now().isoformat(),
                'severity': 'medium'
            },
            {
                'type': 'prophet_forecast',
                'metric_name': 'response_time',
                'anomaly_score': -0.82,
                'timestamp': datetime.now().isoformat(),
                'severity': 'high'
            }
        ]
        
        # Sample self-healing stats
        dashboard_data['self_healing_stats'] = {
            'total_actions_executed': 15,
            'successful_actions': 13,
            'success_rate': 86.7,
            'active_alerts': 3,
            'resolved_alerts': 12,
            'enabled_actions': 6
        }
        
        # Sample log events
        dashboard_data['log_events'] = [
            {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'message': 'Disk space low on /dev/sda1',
                'source': 'systemd',
            },
            {
                'timestamp': datetime.now().isoformat(),
                'level': 'CRITICAL',
                'message': 'Service nginx crashed unexpectedly',
                'source': 'nginx',
            }
        ]
        
        dashboard_data['last_updated'] = datetime.now()
        print("Demo data loaded successfully")
        
    except FileNotFoundError:
        print("Demo data files not found - using minimal data")
        # Create minimal sample data
        dashboard_data['incidents'] = [
            {
                'id': 'incident_1',
                'title': 'High CPU Usage Detected',
                'description': 'CPU usage exceeded 90% threshold',
                'severity': 'high',
                'status': 'open',
                'created_at': datetime.now().isoformat(),
                'affected_services': ['web-server']
            }
        ]

def create_dashboard_template():
    """Create HTML template for dashboard"""
    template_dir = 'templates'
    os.makedirs(template_dir, exist_ok=True)
    
    html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIOps Dashboard - Intelligent Incident Management</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #1a1a1a; 
            color: #ffffff; 
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .header h1 { font-size: 2rem; font-weight: 300; }
        .header .subtitle { opacity: 0.9; margin-top: 0.5rem; }
        .container { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2rem; padding: 2rem; }
        .card {
            background: #2d2d2d;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            border: 1px solid #404040;
        }
        .card h2 { color: #4CAF50; margin-bottom: 1rem; font-size: 1.3rem; }
        .metric { display: flex; justify-content: space-between; margin: 0.5rem 0; }
        .metric-value { font-weight: bold; color: #00f5ff; }
        .status-healthy { color: #4CAF50; }
        .status-warning { color: #ff9800; }
        .status-critical { color: #f44336; }
        .incident-item, .alert-item {
            background: #3d3d3d;
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        .incident-item.high { border-left-color: #ff9800; }
        .incident-item.critical { border-left-color: #f44336; }
        .query-section {
            grid-column: 1 / -1;
            background: #2d2d2d;
            padding: 2rem;
            border-radius: 10px;
            margin-top: 1rem;
        }
        .query-input {
            width: 100%;
            padding: 1rem;
            background: #1a1a1a;
            border: 1px solid #404040;
            border-radius: 5px;
            color: #ffffff;
            font-size: 1rem;
        }
        .query-button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 1rem;
            font-size: 1rem;
        }
        .query-button:hover { background: #45a049; }
        .query-response {
            background: #1a1a1a;
            padding: 1rem;
            border-radius: 5px;
            margin-top: 1rem;
            border-left: 4px solid #00f5ff;
        }
        .refresh-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
        }
        .chart-placeholder {
            background: #1a1a1a;
            height: 150px;
            border-radius: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            margin: 1rem 0;
        }
        @media (max-width: 768px) {
            .container { grid-template-columns: 1fr; }
            .header { padding: 1rem; }
            .header h1 { font-size: 1.5rem; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AIOps Dashboard</h1>
        <div class="subtitle">Autonomous Incident Management & Intelligent Monitoring</div>
    </div>
    
    <div class="refresh-indicator" id="refreshIndicator">
        Live Data • Updated <span id="lastUpdate">just now</span>
    </div>
    
    <div class="container">
        <!-- System Status Card -->
        <div class="card">
            <h2>System Health</h2>
            <div class="metric">
                <span>Health Score</span>
                <span class="metric-value" id="healthScore">85/100</span>
            </div>
            <div class="metric">
                <span>CPU Usage</span>
                <span class="metric-value" id="cpuUsage">45.2%</span>
            </div>
            <div class="metric">
                <span>Memory Usage</span>
                <span class="metric-value" id="memoryUsage">67.8%</span>
            </div>
            <div class="metric">
                <span>Disk Usage</span>
                <span class="metric-value" id="diskUsage">72.1%</span>
            </div>
            <div class="chart-placeholder">CPU/Memory Trend Chart</div>
        </div>
        
        <!-- Incidents Card -->
        <div class="card">
            <h2>Active Incidents</h2>
            <div id="incidentsList">
                <!-- Incidents will be loaded here -->
            </div>
        </div>
        
        <!-- Alerts Card -->
        <div class="card">
            <h2>Recent Alerts</h2>
            <div id="alertsList">
                <!-- Alerts will be loaded here -->
            </div>
        </div>
        
        <!-- ML Insights Card -->
        <div class="card">
            <h2>ML Insights</h2>
            <div class="metric">
                <span>Anomalies Detected</span>
                <span class="metric-value" id="anomaliesCount">2</span>
            </div>
            <div class="metric">
                <span>Prediction Accuracy</span>
                <span class="metric-value">94.2%</span>
            </div>
            <div class="metric">
                <span>Model Status</span>
                <span class="status-healthy">Active</span>
            </div>
            <div class="chart-placeholder">Anomaly Detection Visualization</div>
        </div>
        
        <!-- Self-Healing Card -->
        <div class="card">
            <h2>Self-Healing</h2>
            <div class="metric">
                <span>Actions Executed</span>
                <span class="metric-value" id="actionsExecuted">15</span>
            </div>
            <div class="metric">
                <span>Success Rate</span>
                <span class="metric-value" id="successRate">86.7%</span>
            </div>
            <div class="metric">
                <span>Active Rules</span>
                <span class="metric-value" id="activeRules">6</span>
            </div>
            <div class="chart-placeholder">Action Timeline</div>
        </div>
        
        <!-- Performance Metrics Card -->
        <div class="card">
            <h2>Performance Metrics</h2>
            <div class="metric">
                <span>Response Time</span>
                <span class="metric-value">156ms</span>
            </div>
            <div class="metric">
                <span>Error Rate</span>
                <span class="metric-value status-healthy">0.02%</span>
            </div>
            <div class="metric">
                <span>Throughput</span>
                <span class="metric-value">1,240 req/min</span>
            </div>
            <div class="chart-placeholder">Performance Trends</div>
        </div>
        
        <!-- AI Assistant Query Section -->
        <div class="query-section">
            <h2>🤖 Ask the AI Assistant</h2>
            <input type="text" class="query-input" id="queryInput" 
                   placeholder="Ask about system status, incidents, or anomalies...">
            <button class="query-button" onclick="submitQuery()">Ask AI</button>
            <div class="query-response" id="queryResponse" style="display: none;">
                <!-- AI response will appear here -->
            </div>
        </div>
    </div>
    
    <script>
        // Auto-refresh data every 30 seconds
        setInterval(refreshDashboard, 30000);
        
        // Initial load
        refreshDashboard();
        
        function refreshDashboard() {
            Promise.all([
                fetch('/api/status'),
                fetch('/api/incidents'),
                fetch('/api/alerts'),
                fetch('/api/self-healing')
            ]).then(responses => Promise.all(responses.map(r => r.json())))
            .then(([status, incidents, alerts, selfHealing]) => {
                updateSystemStatus(status);
                updateIncidents(incidents.incidents);
                updateAlerts(alerts.alerts);
                updateSelfHealing(selfHealing);
                updateTimestamp();
            }).catch(err => console.error('Error refreshing dashboard:', err));
        }
        
        function updateSystemStatus(status) {
            document.getElementById('healthScore').textContent = status.health_score + '/100';
            document.getElementById('cpuUsage').textContent = status.cpu_usage + '%';
            document.getElementById('memoryUsage').textContent = status.memory_usage + '%';
            document.getElementById('diskUsage').textContent = status.disk_usage + '%';
        }
        
        function updateIncidents(incidents) {
            const container = document.getElementById('incidentsList');
            container.innerHTML = '';
            
            incidents.slice(-5).forEach(incident => {
                const div = document.createElement('div');
                div.className = `incident-item ${incident.severity}`;
                div.innerHTML = `
                    <div style="font-weight: bold;">${incident.title}</div>
                    <div style="font-size: 0.9em; opacity: 0.8;">
                        ${incident.severity.toUpperCase()} • ${incident.status}
                    </div>
                `;
                container.appendChild(div);
            });
        }
        
        function updateAlerts(alerts) {
            const container = document.getElementById('alertsList');
            container.innerHTML = '';
            
            alerts.slice(-5).forEach(alert => {
                const div = document.createElement('div');
                div.className = 'alert-item';
                div.innerHTML = `
                    <div style="font-weight: bold;">${alert.name}</div>
                    <div style="font-size: 0.9em; opacity: 0.8;">
                        ${alert.severity.toUpperCase()} • ${alert.message}
                    </div>
                `;
                container.appendChild(div);
            });
        }
        
        function updateSelfHealing(data) {
            document.getElementById('actionsExecuted').textContent = data.total_actions_executed || 0;
            document.getElementById('successRate').textContent = (data.success_rate || 0) + '%';
            document.getElementById('activeRules').textContent = data.enabled_actions || 0;
        }
        
        function updateTimestamp() {
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }
        
        function submitQuery() {
            const query = document.getElementById('queryInput').value;
            if (!query.trim()) return;
            
            const responseDiv = document.getElementById('queryResponse');
            responseDiv.style.display = 'block';
            responseDiv.innerHTML = 'Processing query...';
            
            fetch('/api/query', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
            })
            .then(response => response.json())
            .then(data => {
                responseDiv.innerHTML = `
                    <strong>Query:</strong> ${data.query}<br><br>
                    <strong>AI Response:</strong> ${data.response}
                `;
            })
            .catch(err => {
                responseDiv.innerHTML = 'Error processing query: ' + err.message;
            });
        }
        
        // Allow Enter key to submit query
        document.getElementById('queryInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                submitQuery();
            }
        });
    </script>
</body>
</html>
    '''
    
    with open(os.path.join(template_dir, 'dashboard.html'), 'w') as f:
        f.write(html_content)

def run_dashboard():
    """Run the web dashboard"""
    create_dashboard_template()
    load_demo_data()
    
    print("Starting AIOps Web Dashboard...")
    print("Dashboard will be available at: http://localhost:5000")
    print("Features available:")
    print("• Real-time system monitoring")
    print("• Incident and alert visualization") 
    print("• ML insights and anomaly detection")
    print("• Self-healing action tracking")
    print("• AI assistant for natural language queries")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    run_dashboard()