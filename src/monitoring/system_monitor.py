"""
System monitoring and metrics collection
"""
import psutil
import time
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import json
import requests
from prometheus_client.parser import text_string_to_metric_families
import socket
import subprocess

logger = logging.getLogger(__name__)


class SystemMonitor:
    """System monitoring and metrics collection"""
    
    def __init__(self, prometheus_url: Optional[str] = None):
        self.prometheus_url = prometheus_url
        self.metrics_history = []
        self.max_history = 1000
        self.monitoring_interval = 30  # seconds
        
    async def collect_metrics(self) -> List[Dict]:
        """Collect current system metrics"""
        metrics = []
        timestamp = datetime.now()
        
        # System metrics
        system_metrics = self._collect_system_metrics(timestamp)
        metrics.extend(system_metrics)
        
        # Prometheus metrics (if available)
        if self.prometheus_url:
            prom_metrics = await self._collect_prometheus_metrics(timestamp)
            metrics.extend(prom_metrics)
        
        # Network metrics
        network_metrics = self._collect_network_metrics(timestamp)
        metrics.extend(network_metrics)
        
        # Process metrics
        process_metrics = self._collect_process_metrics(timestamp)
        metrics.extend(process_metrics)
        
        # Store in history
        self.metrics_history.extend(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history = self.metrics_history[-self.max_history:]
        
        return metrics
    
    def _collect_system_metrics(self, timestamp: datetime) -> List[Dict]:
        """Collect basic system metrics using psutil"""
        metrics = []
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            metrics.extend([
                {
                    'name': 'cpu_usage_percent',
                    'value': cpu_percent,
                    'timestamp': timestamp,
                    'unit': 'percent',
                    'source': 'psutil',
                    'labels': {'type': 'system'}
                },
                {
                    'name': 'cpu_count',
                    'value': cpu_count,
                    'timestamp': timestamp,
                    'unit': 'count',
                    'source': 'psutil',
                    'labels': {'type': 'system'}
                },
                {
                    'name': 'load_average_1m',
                    'value': load_avg[0],
                    'timestamp': timestamp,
                    'unit': 'load',
                    'source': 'psutil',
                    'labels': {'type': 'system', 'period': '1m'}
                }
            ])
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            metrics.extend([
                {
                    'name': 'memory_usage_percent',
                    'value': memory.percent,
                    'timestamp': timestamp,
                    'unit': 'percent',
                    'source': 'psutil',
                    'labels': {'type': 'memory'}
                },
                {
                    'name': 'memory_available_bytes',
                    'value': memory.available,
                    'timestamp': timestamp,
                    'unit': 'bytes',
                    'source': 'psutil',
                    'labels': {'type': 'memory'}
                },
                {
                    'name': 'memory_used_bytes',
                    'value': memory.used,
                    'timestamp': timestamp,
                    'unit': 'bytes',
                    'source': 'psutil',
                    'labels': {'type': 'memory'}
                },
                {
                    'name': 'swap_usage_percent',
                    'value': swap.percent,
                    'timestamp': timestamp,
                    'unit': 'percent',
                    'source': 'psutil',
                    'labels': {'type': 'swap'}
                }
            ])
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            metrics.extend([
                {
                    'name': 'disk_usage_percent',
                    'value': (disk_usage.used / disk_usage.total) * 100,
                    'timestamp': timestamp,
                    'unit': 'percent',
                    'source': 'psutil',
                    'labels': {'type': 'disk', 'mount': '/'}
                },
                {
                    'name': 'disk_free_bytes',
                    'value': disk_usage.free,
                    'timestamp': timestamp,
                    'unit': 'bytes',
                    'source': 'psutil',
                    'labels': {'type': 'disk', 'mount': '/'}
                }
            ])
            
            if disk_io:
                metrics.extend([
                    {
                        'name': 'disk_read_bytes_total',
                        'value': disk_io.read_bytes,
                        'timestamp': timestamp,
                        'unit': 'bytes',
                        'source': 'psutil',
                        'labels': {'type': 'disk_io', 'operation': 'read'}
                    },
                    {
                        'name': 'disk_write_bytes_total',
                        'value': disk_io.write_bytes,
                        'timestamp': timestamp,
                        'unit': 'bytes',
                        'source': 'psutil',
                        'labels': {'type': 'disk_io', 'operation': 'write'}
                    }
                ])
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def _collect_network_metrics(self, timestamp: datetime) -> List[Dict]:
        """Collect network metrics"""
        metrics = []
        
        try:
            net_io = psutil.net_io_counters()
            net_connections = len(psutil.net_connections())
            
            if net_io:
                metrics.extend([
                    {
                        'name': 'network_bytes_sent_total',
                        'value': net_io.bytes_sent,
                        'timestamp': timestamp,
                        'unit': 'bytes',
                        'source': 'psutil',
                        'labels': {'type': 'network', 'direction': 'sent'}
                    },
                    {
                        'name': 'network_bytes_recv_total',
                        'value': net_io.bytes_recv,
                        'timestamp': timestamp,
                        'unit': 'bytes',
                        'source': 'psutil',
                        'labels': {'type': 'network', 'direction': 'received'}
                    },
                    {
                        'name': 'network_packets_sent_total',
                        'value': net_io.packets_sent,
                        'timestamp': timestamp,
                        'unit': 'packets',
                        'source': 'psutil',
                        'labels': {'type': 'network', 'direction': 'sent'}
                    },
                    {
                        'name': 'network_packets_recv_total',
                        'value': net_io.packets_recv,
                        'timestamp': timestamp,
                        'unit': 'packets',
                        'source': 'psutil',
                        'labels': {'type': 'network', 'direction': 'received'}
                    }
                ])
            
            metrics.append({
                'name': 'network_connections_total',
                'value': net_connections,
                'timestamp': timestamp,
                'unit': 'connections',
                'source': 'psutil',
                'labels': {'type': 'network'}
            })
            
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
        
        return metrics
    
    def _collect_process_metrics(self, timestamp: datetime) -> List[Dict]:
        """Collect process-related metrics"""
        metrics = []
        
        try:
            process_count = len(psutil.pids())
            
            # Top processes by CPU and memory
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage
            top_cpu_processes = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:5]
            # Sort by memory usage
            top_mem_processes = sorted(processes, key=lambda x: x.get('memory_percent', 0), reverse=True)[:5]
            
            metrics.append({
                'name': 'process_count_total',
                'value': process_count,
                'timestamp': timestamp,
                'unit': 'processes',
                'source': 'psutil',
                'labels': {'type': 'process'}
            })
            
            # Add top process metrics
            for i, proc in enumerate(top_cpu_processes):
                metrics.append({
                    'name': f'top_cpu_process_{i+1}_usage',
                    'value': proc.get('cpu_percent', 0),
                    'timestamp': timestamp,
                    'unit': 'percent',
                    'source': 'psutil',
                    'labels': {'type': 'process', 'process_name': proc.get('name', 'unknown'), 'rank': str(i+1)}
                })
            
        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
        
        return metrics
    
    async def _collect_prometheus_metrics(self, timestamp: datetime) -> List[Dict]:
        """Collect metrics from Prometheus endpoint"""
        metrics = []
        
        try:
            response = requests.get(f"{self.prometheus_url}/metrics", timeout=10)
            if response.status_code == 200:
                # Parse Prometheus metrics
                for family in text_string_to_metric_families(response.text):
                    for sample in family.samples:
                        metrics.append({
                            'name': sample.name,
                            'value': sample.value,
                            'timestamp': timestamp,
                            'unit': 'prometheus',
                            'source': 'prometheus',
                            'labels': dict(sample.labels)
                        })
        except Exception as e:
            logger.error(f"Error collecting Prometheus metrics: {e}")
        
        return metrics
    
    def get_historical_metrics(self, hours: int = 24) -> List[Dict]:
        """Get historical metrics for training"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metric for metric in self.metrics_history
            if metric.get('timestamp', datetime.now()) >= cutoff_time
        ]
    
    def get_current_status(self) -> Dict:
        """Get current system status summary"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine health score
            health_score = 100
            if cpu_percent > 80:
                health_score -= 30
            elif cpu_percent > 60:
                health_score -= 15
            
            if memory.percent > 80:
                health_score -= 25
            elif memory.percent > 60:
                health_score -= 10
            
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 90:
                health_score -= 20
            elif disk_percent > 80:
                health_score -= 10
            
            return {
                'timestamp': datetime.now(),
                'health_score': max(0, health_score),
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'disk_usage': disk_percent,
                'uptime': self._get_uptime(),
                'status': 'healthy' if health_score > 70 else 'degraded' if health_score > 40 else 'critical'
            }
            
        except Exception as e:
            logger.error(f"Error getting current status: {e}")
            return {
                'timestamp': datetime.now(),
                'health_score': 0,
                'status': 'error',
                'error': str(e)
            }
    
    def _get_uptime(self) -> float:
        """Get system uptime in seconds"""
        try:
            return time.time() - psutil.boot_time()
        except:
            return 0
    
    def check_service_health(self, service_name: str, port: int = None) -> Dict:
        """Check if a specific service is healthy"""
        try:
            if port:
                # Check if port is open
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    return {'service': service_name, 'status': 'up', 'port': port}
                else:
                    return {'service': service_name, 'status': 'down', 'port': port}
            else:
                # Check if process is running
                for proc in psutil.process_iter(['pid', 'name']):
                    if service_name.lower() in proc.info['name'].lower():
                        return {'service': service_name, 'status': 'up', 'pid': proc.info['pid']}
                
                return {'service': service_name, 'status': 'down'}
                
        except Exception as e:
            return {'service': service_name, 'status': 'error', 'error': str(e)}
    
    def get_log_errors(self, log_file: str = '/var/log/syslog', lines: int = 100) -> List[Dict]:
        """Extract recent errors from log files"""
        errors = []
        
        try:
            if not os.path.exists(log_file):
                return errors
                
            # Use tail to get last N lines
            result = subprocess.run(['tail', '-n', str(lines), log_file], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                error_keywords = ['error', 'exception', 'fail', 'critical', 'panic']
                
                for line in result.stdout.split('\n'):
                    if any(keyword in line.lower() for keyword in error_keywords):
                        errors.append({
                            'timestamp': datetime.now(),  # Could parse actual timestamp from log
                            'level': 'error',
                            'message': line.strip(),
                            'source': log_file
                        })
        
        except Exception as e:
            logger.error(f"Error reading log file {log_file}: {e}")
        
        return errors