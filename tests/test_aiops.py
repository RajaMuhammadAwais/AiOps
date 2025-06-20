#!/usr/bin/env python3
"""
Simple AIOps System Test - Core Functionality Demo
"""
import sys
import os
import json
import asyncio
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

class SimpleAIOpsDemo:
    """Simplified AIOps demonstration focusing on core ML capabilities"""
    
    def __init__(self):
        self.isolation_forest = IsolationForest(contamination='auto', random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        
    def run_complete_demo(self):
        """Run complete AIOps demonstration"""
        console.print(Panel.fit(
            "[bold blue]AIOps - Autonomous Incident Management System[/bold blue]\n"
            "Demonstrating ML-powered anomaly detection and intelligent alerting",
            title="🤖 AIOps Demo"
        ))
        
        # Step 1: Load and display demo data
        self.demo_data_loading()
        
        # Step 2: Train ML models
        self.demo_ml_training()
        
        # Step 3: Detect anomalies
        self.demo_anomaly_detection()
        
        # Step 4: Alert correlation
        self.demo_alert_correlation()
        
        # Step 5: Self-healing simulation
        self.demo_self_healing()
        
        console.print(Panel(
            "[green]AIOps System Demonstration Complete![/green]\n\n"
            "✓ ML-based anomaly detection using Isolation Forest\n"
            "✓ Intelligent alert correlation and noise reduction\n"
            "✓ Automated self-healing action triggers\n"
            "✓ Real-time system monitoring capabilities\n"
            "✓ Pattern recognition and trend analysis\n\n"
            "[blue]Next Steps:[/blue]\n"
            "• Set OPENAI_API_KEY for AI-powered incident analysis\n"
            "• Integrate with Prometheus for production metrics\n"
            "• Configure custom self-healing actions\n"
            "• Deploy web dashboard for visualization",
            title="Demo Summary"
        ))
    
    def demo_data_loading(self):
        """Demonstrate data loading and processing"""
        console.print("\n[bold cyan]Step 1: Data Loading & System Metrics[/bold cyan]")
        
        try:
            # Try to load demo data
            with open('demo_historical_data.json', 'r') as f:
                historical_data = json.load(f)
            with open('demo_current_data.json', 'r') as f:
                current_data = json.load(f)
            with open('demo_alerts.json', 'r') as f:
                alerts_data = json.load(f)
                
            console.print(f"✓ Loaded {len(historical_data)} historical metrics")
            console.print(f"✓ Loaded {len(current_data)} current metrics")
            console.print(f"✓ Loaded {len(alerts_data)} sample alerts")
            
            self.historical_data = historical_data
            self.current_data = current_data
            self.alerts_data = alerts_data
            
        except FileNotFoundError:
            console.print("[yellow]Demo data files not found, generating synthetic data...[/yellow]")
            self.historical_data = self.generate_synthetic_metrics(1000)
            self.current_data = self.generate_synthetic_metrics(50, add_anomalies=True)
            self.alerts_data = self.generate_synthetic_alerts(8)
            
            console.print(f"✓ Generated {len(self.historical_data)} historical metrics")
            console.print(f"✓ Generated {len(self.current_data)} current metrics with anomalies")
            console.print(f"✓ Generated {len(self.alerts_data)} sample alerts")
        
        # Display sample metrics
        table = Table(title="Sample System Metrics")
        table.add_column("Metric Name")
        table.add_column("Value", justify="right")
        table.add_column("Timestamp")
        table.add_column("Service")
        
        for metric in self.current_data[:5]:
            table.add_row(
                metric.get('name', 'unknown')[:20],
                f"{metric.get('value', 0):.2f}",
                str(metric.get('timestamp', ''))[:19],
                metric.get('service', 'unknown')
            )
        
        console.print(table)
    
    def demo_ml_training(self):
        """Demonstrate ML model training"""
        console.print("\n[bold cyan]Step 2: ML Model Training[/bold cyan]")
        
        console.print("Training Isolation Forest for anomaly detection...")
        
        # Prepare training data
        df = pd.DataFrame(self.historical_data)
        numeric_columns = ['value']
        
        if len(df) > 0 and 'value' in df.columns:
            X = df[numeric_columns].fillna(0)
            X_scaled = self.scaler.fit_transform(X)
            self.isolation_forest.fit(X_scaled)
            self.is_trained = True
            
            console.print(f"✓ Trained on {len(df)} historical samples")
            console.print("✓ Model ready for anomaly detection")
        else:
            console.print("[red]Training failed: insufficient data[/red]")
        
        # Display training summary
        table = Table(title="ML Model Configuration")
        table.add_column("Parameter")
        table.add_column("Value")
        
        table.add_row("Algorithm", "Isolation Forest")
        table.add_row("Training Samples", str(len(df)))
        table.add_row("Features", "Metric values")
        table.add_row("Contamination", "Auto-calibrated")
        table.add_row("Status", "✓ Trained" if self.is_trained else "✗ Failed")
        
        console.print(table)
    
    def demo_anomaly_detection(self):
        """Demonstrate anomaly detection"""
        console.print("\n[bold cyan]Step 3: Anomaly Detection[/bold cyan]")
        
        if not self.is_trained:
            console.print("[red]Cannot detect anomalies: model not trained[/red]")
            return
        
        console.print("Analyzing current metrics for anomalies...")
        
        # Detect anomalies in current data
        df_current = pd.DataFrame(self.current_data)
        
        if 'value' in df_current.columns:
            X_current = df_current[['value']].fillna(0)
            X_current_scaled = self.scaler.transform(X_current)
            
            # Get anomaly scores and predictions
            anomaly_scores = self.isolation_forest.decision_function(X_current_scaled)
            is_anomaly = self.isolation_forest.predict(X_current_scaled) == -1
            
            anomalies = []
            for idx, (is_anom, score) in enumerate(zip(is_anomaly, anomaly_scores)):
                if is_anom:
                    anomalies.append({
                        'index': idx,
                        'metric': self.current_data[idx],
                        'anomaly_score': score
                    })
            
            console.print(f"[red]⚠️  Detected {len(anomalies)} anomalies[/red]")
            
            if anomalies:
                table = Table(title="Detected Anomalies")
                table.add_column("Metric")
                table.add_column("Value", justify="right")
                table.add_column("Anomaly Score", justify="right")
                table.add_column("Service")
                
                for anomaly in anomalies[:5]:  # Show top 5
                    metric = anomaly['metric']
                    table.add_row(
                        metric.get('name', 'unknown')[:15],
                        f"{metric.get('value', 0):.2f}",
                        f"{anomaly['anomaly_score']:.3f}",
                        metric.get('service', 'unknown')
                    )
                
                console.print(table)
                
                # Predict incident severity
                severity = self.predict_incident_severity(anomalies)
                console.print(f"[bold]Predicted Incident Severity: {severity.upper()}[/bold]")
            else:
                console.print("[green]✓ No anomalies detected - system operating normally[/green]")
    
    def demo_alert_correlation(self):
        """Demonstrate alert correlation"""
        console.print("\n[bold cyan]Step 4: Alert Correlation & Noise Reduction[/bold cyan]")
        
        console.print(f"Correlating {len(self.alerts_data)} alerts...")
        
        # Simple correlation based on service and timing
        correlated_groups = []
        processed_alerts = set()
        
        for i, alert in enumerate(self.alerts_data):
            if i in processed_alerts:
                continue
                
            group = [alert]
            alert_service = alert.get('labels', {}).get('service', 'unknown')
            alert_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
            
            # Find similar alerts
            for j, other_alert in enumerate(self.alerts_data[i+1:], i+1):
                if j in processed_alerts:
                    continue
                    
                other_service = other_alert.get('labels', {}).get('service', 'unknown')
                other_time = datetime.fromisoformat(other_alert['timestamp'].replace('Z', '+00:00'))
                
                # Group if same service and within 15 minutes
                if (alert_service == other_service and 
                    abs((alert_time - other_time).total_seconds()) < 900):
                    group.append(other_alert)
                    processed_alerts.add(j)
            
            if len(group) > 1:
                correlated_groups.append(group)
            
            processed_alerts.add(i)
        
        unique_alerts = len(self.alerts_data) - sum(len(group)-1 for group in correlated_groups)
        suppressed_count = len(self.alerts_data) - unique_alerts
        noise_reduction = (suppressed_count / len(self.alerts_data)) * 100 if self.alerts_data else 0
        
        table = Table(title="Alert Correlation Results")
        table.add_column("Metric")
        table.add_column("Count", justify="right")
        
        table.add_row("Original Alerts", str(len(self.alerts_data)))
        table.add_row("Correlated Groups", str(len(correlated_groups)))
        table.add_row("Unique Alerts", str(unique_alerts))
        table.add_row("Suppressed (Noise)", str(suppressed_count))
        
        console.print(table)
        console.print(f"[green]✓ Achieved {noise_reduction:.1f}% noise reduction[/green]")
    
    def demo_self_healing(self):
        """Demonstrate self-healing actions"""
        console.print("\n[bold cyan]Step 5: Self-healing Actions[/bold cyan]")
        
        # Simulate self-healing decision logic
        actions_taken = []
        
        # Check for high CPU scenarios
        high_cpu_metrics = [m for m in self.current_data 
                          if 'cpu' in m.get('name', '').lower() and m.get('value', 0) > 80]
        
        if high_cpu_metrics:
            actions_taken.append({
                'action': 'Restart High CPU Service',
                'trigger': f'CPU usage {high_cpu_metrics[0]["value"]:.1f}% > 80%',
                'status': 'Simulated',
                'result': 'Service restart scheduled'
            })
        
        # Check for memory issues
        high_memory_metrics = [m for m in self.current_data 
                             if 'memory' in m.get('name', '').lower() and m.get('value', 0) > 85]
        
        if high_memory_metrics:
            actions_taken.append({
                'action': 'Clear Cache',
                'trigger': f'Memory usage {high_memory_metrics[0]["value"]:.1f}% > 85%',
                'status': 'Simulated',
                'result': 'Cache clearing initiated'
            })
        
        # Check for critical alerts
        critical_alerts = [a for a in self.alerts_data if a.get('severity') == 'critical']
        
        if critical_alerts:
            actions_taken.append({
                'action': 'Alert Team',
                'trigger': f'{len(critical_alerts)} critical alerts',
                'status': 'Simulated',
                'result': 'Team notification sent'
            })
        
        if actions_taken:
            table = Table(title="Self-healing Actions Triggered")
            table.add_column("Action")
            table.add_column("Trigger Condition")
            table.add_column("Status")
            table.add_column("Result")
            
            for action in actions_taken:
                table.add_row(
                    action['action'],
                    action['trigger'],
                    action['status'],
                    action['result']
                )
            
            console.print(table)
            console.print(f"[green]✓ Executed {len(actions_taken)} self-healing actions[/green]")
        else:
            console.print("[blue]No self-healing actions required - system stable[/blue]")
        
        # Display self-healing capabilities
        console.print("\n[bold]Available Self-healing Actions:[/bold]")
        capabilities = [
            "• Restart services on high resource usage",
            "• Clear caches on memory pressure", 
            "• Scale services on high load",
            "• Alert teams on critical incidents",
            "• Rollback deployments on errors",
            "• Run custom remediation scripts"
        ]
        
        for capability in capabilities:
            console.print(capability)
    
    def predict_incident_severity(self, anomalies):
        """Predict incident severity based on anomalies"""
        if not anomalies:
            return "low"
        
        # Calculate severity score
        severity_score = 0
        severity_score += min(len(anomalies) * 10, 40)  # Number of anomalies
        
        avg_score = np.mean([abs(a['anomaly_score']) for a in anomalies])
        severity_score += avg_score * 30
        
        # Check for critical metrics
        for anomaly in anomalies:
            metric_name = anomaly['metric'].get('name', '').lower()
            if any(critical in metric_name for critical in ['cpu', 'memory', 'disk', 'error']):
                severity_score += 15
        
        if severity_score >= 80:
            return "critical"
        elif severity_score >= 60:
            return "high"
        elif severity_score >= 30:
            return "medium"
        else:
            return "low"
    
    def generate_synthetic_metrics(self, count, add_anomalies=False):
        """Generate synthetic metrics for demo"""
        import random
        
        metrics = []
        services = ['web-server', 'database', 'cache', 'api-gateway', 'auth-service']
        metric_types = ['cpu_usage', 'memory_usage', 'disk_usage', 'response_time', 'error_rate']
        
        base_time = datetime.now() - timedelta(hours=24)
        
        for i in range(count):
            service = random.choice(services)
            metric_type = random.choice(metric_types)
            
            # Generate realistic baseline values
            if metric_type in ['cpu_usage', 'memory_usage', 'disk_usage']:
                baseline = random.uniform(20, 70)
            elif metric_type == 'response_time':
                baseline = random.uniform(50, 200)
            else:  # error_rate
                baseline = random.uniform(0.1, 2.0)
            
            # Add anomalies for current data
            if add_anomalies and random.random() < 0.2:  # 20% chance
                value = baseline * random.uniform(2, 4)
            else:
                value = baseline + random.gauss(0, baseline * 0.1)
            
            metrics.append({
                'name': f'{service}_{metric_type}',
                'value': max(0, value),
                'timestamp': base_time + timedelta(minutes=i),
                'service': service,
                'metric_type': metric_type,
                'source': 'synthetic'
            })
        
        return metrics
    
    def generate_synthetic_alerts(self, count):
        """Generate synthetic alerts for demo"""
        import random
        
        alerts = []
        services = ['web-server', 'database', 'cache', 'api-gateway']
        severities = ['low', 'medium', 'high', 'critical']
        messages = [
            'High CPU usage detected',
            'Memory usage above threshold',
            'Response time degraded',
            'Error rate increased',
            'Service unreachable'
        ]
        
        for i in range(count):
            alerts.append({
                'id': f'alert_{i}',
                'name': f'{random.choice(services)} Alert',
                'severity': random.choice(severities),
                'message': random.choice(messages),
                'timestamp': (datetime.now() - timedelta(minutes=random.randint(0, 60))).isoformat(),
                'labels': {
                    'service': random.choice(services),
                    'environment': 'production'
                }
            })
        
        return alerts

def main():
    """Run the AIOps demonstration"""
    demo = SimpleAIOpsDemo()
    demo.run_complete_demo()

if __name__ == '__main__':
    main()