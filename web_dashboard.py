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
    'last_updated': datetime.now()
}

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