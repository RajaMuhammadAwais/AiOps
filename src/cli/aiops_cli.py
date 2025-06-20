#!/usr/bin/env python3
"""
AIOps CLI - Command Line Interface for Autonomous Incident Management
"""
import click
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich.text import Text
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.incident import Incident, Alert, IncidentSeverity, IncidentStatus, AlertSource
from ml.anomaly_detector import AnomalyDetector
from ml.alert_correlator import AlertCorrelator
from monitoring.system_monitor import SystemMonitor
from alerting.alert_manager import AlertManager
from chatops.llm_assistant import LLMAssistant

console = Console()


class AIOpsController:
    """Main controller for AIOps operations"""
    
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.alert_correlator = AlertCorrelator()
        self.system_monitor = SystemMonitor()
        self.alert_manager = AlertManager()
        self.llm_assistant = LLMAssistant()
        self.incidents = []
        self.alerts = []
        
    async def initialize(self):
        """Initialize all components"""
        console.print("[blue]Initializing AIOps system...[/blue]")
        
        # Load historical data for training
        historical_data = self.system_monitor.get_historical_metrics()
        if historical_data:
            console.print(f"Training anomaly detector with {len(historical_data)} historical samples...")
            self.anomaly_detector.train_baseline(historical_data)
        
        console.print("[green]✓ AIOps system initialized successfully[/green]")
    
    async def start_monitoring(self):
        """Start real-time monitoring"""
        console.print("[yellow]Starting real-time monitoring...[/yellow]")
        
        try:
            while True:
                # Collect current metrics
                current_metrics = await self.system_monitor.collect_metrics()
                
                # Detect anomalies
                anomalies = self.anomaly_detector.detect_anomalies(current_metrics)
                
                if anomalies:
                    console.print(f"[red]⚠️  Detected {len(anomalies)} anomalies[/red]")
                    
                    # Convert anomalies to alerts
                    new_alerts = self._anomalies_to_alerts(anomalies)
                    self.alerts.extend(new_alerts)
                    
                    # Correlate alerts
                    correlation_result = self.alert_correlator.correlate_alerts(self.alerts[-50:])  # Last 50 alerts
                    
                    # Create incidents from unique alerts
                    for alert in correlation_result['unique_alerts']:
                        incident = await self._create_incident_from_alert(alert, anomalies)
                        self.incidents.append(incident)
                        console.print(f"[red]🚨 New incident created: {incident.title}[/red]")
                
                # Sleep for monitoring interval
                await asyncio.sleep(30)  # 30 seconds
                
        except KeyboardInterrupt:
            console.print("[yellow]Monitoring stopped by user[/yellow]")
    
    def _anomalies_to_alerts(self, anomalies: List[Dict]) -> List[Alert]:
        """Convert anomaly detections to alerts"""
        alerts = []
        for anomaly in anomalies:
            severity = self.anomaly_detector.predict_incident_severity([anomaly], {})
            
            alert = Alert(
                id=f"alert_{datetime.now().timestamp()}",
                name=f"Anomaly detected: {anomaly.get('metric_name', 'unknown')}",
                severity=IncidentSeverity(severity),
                source=AlertSource.SYSTEM,
                timestamp=datetime.now(),
                message=f"Anomaly detected with score {anomaly.get('anomaly_score', 0):.3f}",
                labels={"type": anomaly.get('type', 'unknown')},
                metrics=[anomaly]
            )
            alerts.append(alert)
        
        return alerts
    
    async def _create_incident_from_alert(self, alert: Alert, anomalies: List[Dict]) -> Incident:
        """Create incident from alert with AI analysis"""
        
        # Get AI explanation
        alert_dict = {
            'id': alert.id,
            'name': alert.name,
            'severity': alert.severity.value,
            'source': alert.source.value,
            'message': alert.message,
            'labels': alert.labels,
            'metrics': alert.metrics
        }
        explanation = await self.llm_assistant.explain_incident(alert_dict, anomalies)
        
        incident = Incident(
            id=f"incident_{datetime.now().timestamp()}",
            title=f"System anomaly: {alert.name}",
            description=explanation.get('description', alert.message),
            severity=alert.severity,
            status=IncidentStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            alerts=[alert],
            llm_explanation=explanation.get('explanation'),
            root_cause_analysis=explanation.get('root_cause'),
            predicted_resolution_time=explanation.get('predicted_time')
        )
        
        return incident


@click.group()
@click.pass_context
def cli(ctx):
    """AIOps - Autonomous Incident Management System"""
    ctx.ensure_object(dict)
    ctx.obj['controller'] = AIOpsController()


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize the AIOps system"""
    controller = ctx.obj['controller']
    asyncio.run(controller.initialize())


@cli.command()
@click.option('--duration', '-d', default=0, help='Monitoring duration in minutes (0 for continuous)')
@click.pass_context
def monitor(ctx, duration):
    """Start real-time monitoring"""
    controller = ctx.obj['controller']
    
    console.print(Panel.fit(
        "[bold blue]AIOps Real-time Monitoring[/bold blue]\n"
        "Press Ctrl+C to stop monitoring",
        title="🔍 Monitoring"
    ))
    
    asyncio.run(controller.start_monitoring())


@cli.command()
@click.pass_context
def status(ctx):
    """Show current system status"""
    controller = ctx.obj['controller']
    
    # Create status table
    table = Table(title="AIOps System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")
    
    # Check component status
    table.add_row("Anomaly Detector", "🟢 Active", f"Trained: {controller.anomaly_detector.is_trained}")
    table.add_row("Alert Correlator", "🟢 Active", f"Threshold: {controller.alert_correlator.similarity_threshold}")
    table.add_row("System Monitor", "🟢 Active", "Collecting metrics")
    table.add_row("LLM Assistant", "🟢 Ready", "GPT-4 powered analysis")
    
    console.print(table)
    
    # Show recent incidents
    if controller.incidents:
        console.print("\n[bold]Recent Incidents:[/bold]")
        for incident in controller.incidents[-5:]:
            severity_color = {
                "critical": "red",
                "high": "yellow", 
                "medium": "blue",
                "low": "green"
            }.get(incident.severity.value, "white")
            
            console.print(f"[{severity_color}]• {incident.title}[/{severity_color}] - {incident.status.value}")


@cli.command()
@click.argument('query')
@click.pass_context
def ask(ctx, query):
    """Ask the AI assistant about incidents or system status"""
    controller = ctx.obj['controller']
    
    console.print(f"[blue]🤖 Processing query: {query}[/blue]")
    
    # Use LLM assistant to answer the query
    response = asyncio.run(controller.llm_assistant.chat_query(query, {
        'incidents': controller.incidents[-10:],
        'alerts': controller.alerts[-20:],
        'system_status': controller.system_monitor.get_current_status()
    }))
    
    console.print(Panel(response, title="AI Assistant Response", border_style="green"))


@cli.command()
@click.pass_context
def incidents(ctx):
    """List recent incidents"""
    controller = ctx.obj['controller']
    
    if not controller.incidents:
        console.print("[yellow]No incidents found[/yellow]")
        return
    
    table = Table(title="Recent Incidents")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Severity", style="bold")
    table.add_column("Status")
    table.add_column("Created", style="dim")
    
    for incident in controller.incidents[-10:]:
        severity_style = {
            "critical": "red",
            "high": "yellow",
            "medium": "blue", 
            "low": "green"
        }.get(incident.severity.value, "white")
        
        table.add_row(
            incident.id[:8],
            incident.title[:50],
            f"[{severity_style}]{incident.severity.value.upper()}[/{severity_style}]",
            incident.status.value,
            incident.created_at.strftime("%H:%M:%S")
        )
    
    console.print(table)


@cli.command()
@click.argument('incident_id')
@click.pass_context
def describe(ctx, incident_id):
    """Get detailed description of an incident"""
    controller = ctx.obj['controller']
    
    # Find incident
    incident = None
    for inc in controller.incidents:
        if inc.id.startswith(incident_id):
            incident = inc
            break
    
    if not incident:
        console.print(f"[red]Incident {incident_id} not found[/red]")
        return
    
    # Display incident details
    panel_content = f"""
[bold]Title:[/bold] {incident.title}
[bold]Severity:[/bold] {incident.severity.value.upper()}
[bold]Status:[/bold] {incident.status.value}
[bold]Created:[/bold] {incident.created_at}

[bold]Description:[/bold]
{incident.description}

[bold]AI Analysis:[/bold]
{incident.llm_explanation or 'No AI analysis available'}

[bold]Root Cause:[/bold]
{incident.root_cause_analysis or 'Analysis in progress...'}
    """
    
    console.print(Panel(panel_content, title=f"Incident {incident.id[:8]}", border_style="red"))


@cli.command()
@click.option('--cpu', is_flag=True, help='Show CPU metrics')
@click.option('--memory', is_flag=True, help='Show memory metrics') 
@click.option('--disk', is_flag=True, help='Show disk metrics')
@click.pass_context
def metrics(ctx, cpu, memory, disk):
    """Display current system metrics"""
    controller = ctx.obj['controller']
    
    current_metrics = asyncio.run(controller.system_monitor.collect_metrics())
    
    if not current_metrics:
        console.print("[yellow]No metrics available[/yellow]")
        return
    
    # Filter metrics based on flags
    filtered_metrics = current_metrics
    if cpu or memory or disk:
        filtered_metrics = []
        for metric in current_metrics:
            name = metric.get('name', '').lower()
            if (cpu and 'cpu' in name) or \
               (memory and 'memory' in name) or \
               (disk and 'disk' in name):
                filtered_metrics.append(metric)
    
    # Display metrics table
    table = Table(title="Current System Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Unit")
    table.add_column("Source", style="dim")
    
    for metric in filtered_metrics:
        table.add_row(
            metric.get('name', 'unknown'),
            f"{metric.get('value', 0):.2f}",
            metric.get('unit', ''),
            metric.get('source', 'system')
        )
    
    console.print(table)


if __name__ == '__main__':
    cli()