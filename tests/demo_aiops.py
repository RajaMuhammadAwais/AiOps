#!/usr/bin/env python3
"""
AIOps System Demo - Autonomous Incident Management
"""
import sys
import os
import asyncio
import json
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track
import time

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.incident import Incident, Alert, IncidentSeverity, IncidentStatus, AlertSource
from ml.anomaly_detector import AnomalyDetector
from ml.alert_correlator import AlertCorrelator
from monitoring.system_monitor import SystemMonitor
from alerting.alert_manager import AlertManager
from chatops.llm_assistant import LLMAssistant

console = Console()

class AIOpsDemo:
    """Demonstration of AIOps capabilities"""
    
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.alert_correlator = AlertCorrelator()
        self.system_monitor = SystemMonitor()
        self.alert_manager = AlertManager()
        self.llm_assistant = LLMAssistant()
        
    async def run_demo(self):
        """Run complete AIOps demonstration"""
        console.print(Panel.fit(
            "[bold blue]AIOps Autonomous Incident Management Demo[/bold blue]\n"
            "Demonstrating ML-powered monitoring, correlation, and self-healing",
            title="🤖 AIOps System"
        ))
        
        # Demo 1: System Status
        await self.demo_system_status()
        
        # Demo 2: Anomaly Detection Training
        await self.demo_anomaly_training()
        
        # Demo 3: Real-time Monitoring
        await self.demo_monitoring()
        
        # Demo 4: Alert Correlation
        await self.demo_alert_correlation()
        
        # Demo 5: Self-healing Actions
        await self.demo_self_healing()
        
        # Demo 6: AI Assistant
        await self.demo_ai_assistant()
        
        console.print(Panel(
            "[green]Demo completed! The AIOps system demonstrates:[/green]\n"
            "✓ ML-based anomaly detection\n"
            "✓ Intelligent alert correlation\n"
            "✓ Automated self-healing actions\n"
            "✓ AI-powered incident analysis\n"
            "✓ Real-time system monitoring",
            title="Demo Summary"
        ))
    
    async def demo_system_status(self):
        """Demonstrate system status monitoring"""
        console.print("\n[bold cyan]Demo 1: System Status Monitoring[/bold cyan]")
        
        # Get current system status
        status = self.system_monitor.get_current_status()
        
        table = Table(title="Current System Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Status")
        
        table.add_row("Health Score", f"{status['health_score']:.1f}/100", 
                     "🟢 Healthy" if status['health_score'] > 70 else "🟡 Degraded")
        table.add_row("CPU Usage", f"{status['cpu_usage']:.1f}%", 
                     "Normal" if status['cpu_usage'] < 80 else "High")
        table.add_row("Memory Usage", f"{status['memory_usage']:.1f}%", 
                     "Normal" if status['memory_usage'] < 80 else "High")
        table.add_row("Disk Usage", f"{status['disk_usage']:.1f}%", 
                     "Normal" if status['disk_usage'] < 90 else "Critical")
        
        console.print(table)
        time.sleep(2)
    
    async def demo_anomaly_training(self):
        """Demonstrate anomaly detection training"""
        console.print("\n[bold cyan]Demo 2: ML Anomaly Detection Training[/bold cyan]")
        
        try:
            # Load demo historical data
            with open('demo_historical_data.json', 'r') as f:
                historical_data = json.load(f)
            
            console.print(f"Loading {len(historical_data)} historical metrics for training...")
            
            # Train the anomaly detector
            for _ in track(range(1), description="Training ML models..."):
                self.anomaly_detector.train_baseline(historical_data[:1000])  # Subset for demo
                time.sleep(1)
            
            model_info = self.anomaly_detector.get_model_info()
            console.print(f"✓ Trained {model_info['model_type']} with {len(historical_data)} samples")
            
        except FileNotFoundError:
            console.print("[yellow]Historical data not found. Run demo_data_generator.py first[/yellow]")
            # Generate minimal data for demo
            historical_data = self._generate_minimal_data()
            self.anomaly_detector.train_baseline(historical_data)
            console.print("✓ Trained with minimal demo data")
        
        time.sleep(2)
    
    async def demo_monitoring(self):
        """Demonstrate real-time monitoring"""
        console.print("\n[bold cyan]Demo 3: Real-time Monitoring & Anomaly Detection[/bold cyan]")
        
        try:
            # Load current metrics with anomalies
            with open('demo_current_data.json', 'r') as f:
                current_metrics = json.load(f)
        except FileNotFoundError:
            current_metrics = self._generate_minimal_data()
        
        console.print("Analyzing current metrics for anomalies...")
        
        # Detect anomalies
        anomalies = self.anomaly_detector.detect_anomalies(current_metrics[:10])
        
        if anomalies:
            console.print(f"[red]⚠️  Detected {len(anomalies)} anomalies:[/red]")
            
            table = Table()
            table.add_column("Type")
            table.add_column("Metric")
            table.add_column("Anomaly Score", justify="right")
            
            for anomaly in anomalies[:5]:  # Show first 5
                table.add_row(
                    anomaly.get('type', 'unknown'),
                    anomaly.get('metric_name', 'unknown'),
                    f"{anomaly.get('anomaly_score', 0):.3f}"
                )
            
            console.print(table)
        else:
            console.print("[green]✓ No anomalies detected - system operating normally[/green]")
        
        time.sleep(2)
    
    async def demo_alert_correlation(self):
        """Demonstrate alert correlation and noise reduction"""
        console.print("\n[bold cyan]Demo 4: Alert Correlation & Noise Reduction[/bold cyan]")
        
        try:
            # Load demo alerts
            with open('demo_alerts.json', 'r') as f:
                alerts = json.load(f)
        except FileNotFoundError:
            alerts = self._generate_sample_alerts()
        
        console.print(f"Processing {len(alerts)} alerts for correlation...")
        
        # Correlate alerts
        correlation_result = self.alert_correlator.correlate_alerts(alerts)
        
        table = Table(title="Alert Correlation Results")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        table.add_column("Details")
        
        table.add_row("Original Alerts", str(len(alerts)), "Raw alerts received")
        table.add_row("Unique Alerts", str(len(correlation_result['unique_alerts'])), "After correlation")
        table.add_row("Suppressed (Noise)", str(len(correlation_result['suppressed_alerts'])), "Duplicate/noisy alerts")
        table.add_row("Correlated Groups", str(len(correlation_result['correlated_groups'])), "Related alert clusters")
        
        console.print(table)
        
        noise_reduction = correlation_result['noise_reduction_ratio'] * 100
        console.print(f"[green]✓ Achieved {noise_reduction:.1f}% noise reduction[/green]")
        
        time.sleep(2)
    
    async def demo_self_healing(self):
        """Demonstrate self-healing actions"""
        console.print("\n[bold cyan]Demo 5: Self-healing Actions[/bold cyan]")
        
        # Create a sample critical alert
        sample_alert = {
            'id': 'demo_critical_alert',
            'name': 'High CPU Usage',
            'severity': 'critical',
            'message': 'CPU usage above 90% for 5 minutes',
            'labels': {'service': 'web-server'},
            'metrics': [{'name': 'cpu_usage', 'value': 95.0}]
        }
        
        console.print("Processing critical alert for self-healing...")
        
        # Process alert through alert manager
        result = await self.alert_manager.process_alert(sample_alert)
        
        table = Table(title="Self-healing Response")
        table.add_column("Action")
        table.add_column("Status")
        table.add_column("Details")
        
        if result['actions_taken']:
            for action in result['actions_taken']:
                status = "✓ Success" if action['result'].get('success') else "✗ Failed"
                table.add_row(
                    action['action'],
                    status,
                    action['result'].get('message', 'No details')
                )
        else:
            table.add_row("No Actions", "N/A", "No conditions met for self-healing")
        
        console.print(table)
        
        # Show self-healing stats
        stats = self.alert_manager.get_self_healing_stats()
        console.print(f"[blue]Self-healing Statistics:[/blue]")
        console.print(f"• Enabled Actions: {stats['enabled_actions']}")
        console.print(f"• Success Rate: {stats['success_rate']:.1f}%")
        
        time.sleep(2)
    
    async def demo_ai_assistant(self):
        """Demonstrate AI assistant capabilities"""
        console.print("\n[bold cyan]Demo 6: AI-Powered Incident Analysis[/bold cyan]")
        
        if not self.llm_assistant.is_available():
            console.print("[yellow]AI Assistant Demo: Requires OPENAI_API_KEY[/yellow]")
            console.print("Set your OpenAI API key to enable:")
            console.print("export OPENAI_API_KEY='your-key-here'")
            return
        
        # Sample incident for AI analysis
        sample_incident = {
            'name': 'Database Connection Timeout',
            'severity': 'high',
            'message': 'Multiple connection timeouts to primary database',
            'labels': {'service': 'database', 'environment': 'production'}
        }
        
        sample_anomalies = [
            {'type': 'response_time', 'metric_name': 'db_response_time', 'anomaly_score': -0.8},
            {'type': 'connection_pool', 'metric_name': 'db_connections', 'anomaly_score': -0.6}
        ]
        
        console.print("Requesting AI analysis of incident...")
        
        try:
            analysis = await self.llm_assistant.explain_incident(sample_incident, sample_anomalies)
            
            console.print(Panel(
                f"[bold]Root Cause:[/bold] {analysis.get('root_cause', 'Analysis unavailable')}\n\n"
                f"[bold]Explanation:[/bold] {analysis.get('explanation', 'No explanation provided')}\n\n"
                f"[bold]Estimated Resolution:[/bold] {analysis.get('predicted_time', 'Unknown')} minutes",
                title="AI Incident Analysis"
            ))
            
        except Exception as e:
            console.print(f"[red]AI Analysis Error: {e}[/red]")
        
        time.sleep(2)
    
    def _generate_minimal_data(self):
        """Generate minimal data for demo when files don't exist"""
        import random
        from datetime import timedelta
        
        data = []
        base_time = datetime.now() - timedelta(hours=1)
        
        for i in range(100):
            data.append({
                'name': f'demo_metric_{i % 5}',
                'value': random.uniform(10, 90) + (50 if i % 20 == 0 else 0),  # Add some anomalies
                'timestamp': base_time + timedelta(minutes=i),
                'source': 'demo'
            })
        
        return data
    
    def _generate_sample_alerts(self):
        """Generate sample alerts for demo"""
        return [
            {
                'id': f'alert_{i}',
                'name': f'Sample Alert {i}',
                'severity': 'medium',
                'message': 'Demo alert message',
                'timestamp': datetime.now(),
                'labels': {'service': f'service_{i % 3}'}
            }
            for i in range(6)
        ]

async def main():
    """Main demo execution"""
    demo = AIOpsDemo()
    await demo.run_demo()

if __name__ == '__main__':
    asyncio.run(main())