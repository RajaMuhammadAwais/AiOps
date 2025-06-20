#!/usr/bin/env python3
"""
Demo data generator for AIOps system testing
"""
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict
import json

class DemoDataGenerator:
    """Generate realistic demo data for AIOps system testing"""
    
    def __init__(self):
        self.services = ['web-server', 'database', 'cache', 'api-gateway', 'auth-service']
        self.metric_types = ['cpu_usage', 'memory_usage', 'disk_usage', 'response_time', 'error_rate']
        self.error_messages = [
            'Connection timeout to database',
            'High CPU usage detected',
            'Memory usage above threshold',
            'API response time degraded',
            'Authentication service unreachable',
            'Disk space critically low',
            'Network connectivity issues'
        ]
    
    def generate_historical_metrics(self, days: int = 7, samples_per_hour: int = 4) -> List[Dict]:
        """Generate historical metrics for training"""
        metrics = []
        start_time = datetime.now() - timedelta(days=days)
        
        for day in range(days):
            for hour in range(24):
                for sample in range(samples_per_hour):
                    timestamp = start_time + timedelta(
                        days=day,
                        hours=hour,
                        minutes=sample * (60 // samples_per_hour)
                    )
                    
                    for service in self.services:
                        for metric_type in self.metric_types:
                            # Generate realistic baseline values with some noise
                            baseline = self._get_baseline_value(metric_type, hour)
                            noise = random.gauss(0, baseline * 0.1)
                            value = max(0, baseline + noise)
                            
                            # Add occasional anomalies (5% chance)
                            if random.random() < 0.05:
                                value = self._add_anomaly(metric_type, value)
                            
                            metrics.append({
                                'name': f'{service}_{metric_type}',
                                'value': value,
                                'timestamp': timestamp,
                                'unit': self._get_unit(metric_type),
                                'source': 'demo',
                                'service': service,
                                'metric_type': metric_type
                            })
        
        return metrics
    
    def generate_current_metrics(self, anomaly_probability: float = 0.1) -> List[Dict]:
        """Generate current metrics with optional anomalies"""
        metrics = []
        timestamp = datetime.now()
        current_hour = timestamp.hour
        
        for service in self.services:
            for metric_type in self.metric_types:
                baseline = self._get_baseline_value(metric_type, current_hour)
                noise = random.gauss(0, baseline * 0.05)
                value = max(0, baseline + noise)
                
                # Add anomalies based on probability
                if random.random() < anomaly_probability:
                    value = self._add_anomaly(metric_type, value)
                
                metrics.append({
                    'name': f'{service}_{metric_type}',
                    'value': value,
                    'timestamp': timestamp,
                    'unit': self._get_unit(metric_type),
                    'source': 'demo',
                    'service': service,
                    'metric_type': metric_type
                })
        
        return metrics
    
    def generate_alerts(self, num_alerts: int = 5) -> List[Dict]:
        """Generate sample alerts"""
        alerts = []
        severities = ['low', 'medium', 'high', 'critical']
        
        for i in range(num_alerts):
            service = random.choice(self.services)
            message = random.choice(self.error_messages)
            severity = random.choice(severities)
            
            # Higher severity alerts are less common
            if severity == 'critical':
                if random.random() > 0.1:  # 10% chance
                    severity = 'high'
            elif severity == 'high':
                if random.random() > 0.2:  # 20% chance
                    severity = 'medium'
            
            alert = {
                'id': f'alert_{int(time.time())}_{i}',
                'name': f'{service} Alert',
                'severity': severity,
                'source': 'system',
                'timestamp': datetime.now() - timedelta(minutes=random.randint(0, 120)),
                'message': message,
                'labels': {
                    'service': service,
                    'environment': 'production',
                    'region': random.choice(['us-east-1', 'us-west-2', 'eu-west-1'])
                },
                'metrics': []
            }
            alerts.append(alert)
        
        return alerts
    
    def _get_baseline_value(self, metric_type: str, hour: int) -> float:
        """Get baseline value for metric type with time-based patterns"""
        # Simulate daily patterns
        if metric_type == 'cpu_usage':
            # Higher CPU during business hours
            if 9 <= hour <= 17:
                return random.uniform(30, 60)
            else:
                return random.uniform(10, 30)
        
        elif metric_type == 'memory_usage':
            # Gradually increasing memory usage
            return random.uniform(40, 70)
        
        elif metric_type == 'disk_usage':
            # Slowly growing disk usage
            return random.uniform(60, 80)
        
        elif metric_type == 'response_time':
            # Higher response times during peak hours
            if 9 <= hour <= 17:
                return random.uniform(100, 300)  # milliseconds
            else:
                return random.uniform(50, 150)
        
        elif metric_type == 'error_rate':
            # Low error rate normally
            return random.uniform(0.1, 2.0)  # percentage
        
        return random.uniform(0, 100)
    
    def _add_anomaly(self, metric_type: str, baseline_value: float) -> float:
        """Add anomaly to metric value"""
        if metric_type in ['cpu_usage', 'memory_usage', 'disk_usage']:
            # Spike anomaly
            return min(100, baseline_value * random.uniform(2, 4))
        
        elif metric_type == 'response_time':
            # Response time spike
            return baseline_value * random.uniform(3, 8)
        
        elif metric_type == 'error_rate':
            # Error rate spike
            return min(50, baseline_value * random.uniform(5, 15))
        
        return baseline_value * random.uniform(1.5, 3)
    
    def _get_unit(self, metric_type: str) -> str:
        """Get unit for metric type"""
        units = {
            'cpu_usage': 'percent',
            'memory_usage': 'percent', 
            'disk_usage': 'percent',
            'response_time': 'milliseconds',
            'error_rate': 'percent'
        }
        return units.get(metric_type, 'unknown')

if __name__ == '__main__':
    generator = DemoDataGenerator()
    
    # Generate and save demo data
    print("Generating historical metrics...")
    historical = generator.generate_historical_metrics(days=3)
    with open('demo_historical_data.json', 'w') as f:
        json.dump(historical, f, indent=2, default=str)
    print(f"Generated {len(historical)} historical metrics")
    
    print("\nGenerating current metrics with anomalies...")
    current = generator.generate_current_metrics(anomaly_probability=0.3)
    with open('demo_current_data.json', 'w') as f:
        json.dump(current, f, indent=2, default=str)
    print(f"Generated {len(current)} current metrics")
    
    print("\nGenerating sample alerts...")
    alerts = generator.generate_alerts(num_alerts=8)
    with open('demo_alerts.json', 'w') as f:
        json.dump(alerts, f, indent=2, default=str)
    print(f"Generated {len(alerts)} sample alerts")
    
    print("\nDemo data generated successfully!")