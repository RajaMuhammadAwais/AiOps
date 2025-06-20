"""
Distributed Tracing and Advanced Observability for AIOps
Enterprise-grade service mesh monitoring and trace analysis
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Distributed trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    start_time: datetime
    duration_ms: float
    status: str  # success, error, timeout
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)


@dataclass
class Trace:
    """Complete distributed trace"""
    trace_id: str
    spans: List[Span]
    start_time: datetime
    total_duration_ms: float
    service_count: int
    error_count: int
    critical_path: List[str] = field(default_factory=list)


class DistributedTracingAnalyzer:
    """Advanced distributed tracing analysis for AIOps"""
    
    def __init__(self):
        self.traces = {}
        self.service_dependencies = nx.DiGraph()
        self.performance_baselines = {}
        self.anomaly_patterns = {}
        
    async def analyze_trace_patterns(self, traces: List[Trace]) -> Dict:
        """Analyze patterns in distributed traces for insights"""
        
        # Build service dependency graph
        self._build_service_graph(traces)
        
        # Analyze performance patterns
        performance_analysis = self._analyze_performance_patterns(traces)
        
        # Detect anomalous traces
        anomaly_analysis = self._detect_trace_anomalies(traces)
        
        # Identify bottlenecks
        bottleneck_analysis = self._identify_service_bottlenecks(traces)
        
        # Error propagation analysis
        error_analysis = self._analyze_error_propagation(traces)
        
        return {
            "service_topology": self._export_service_topology(),
            "performance_insights": performance_analysis,
            "anomaly_detection": anomaly_analysis,
            "bottleneck_analysis": bottleneck_analysis,
            "error_propagation": error_analysis,
            "optimization_recommendations": self._generate_optimization_recommendations(
                performance_analysis, bottleneck_analysis
            )
        }
    
    def _build_service_graph(self, traces: List[Trace]):
        """Build service dependency graph from traces"""
        
        for trace in traces:
            # Sort spans by start time to understand call flow
            sorted_spans = sorted(trace.spans, key=lambda s: s.start_time)
            
            for i, span in enumerate(sorted_spans):
                # Add service node if not exists
                if not self.service_dependencies.has_node(span.service_name):
                    self.service_dependencies.add_node(
                        span.service_name,
                        operations=set(),
                        avg_latency=0,
                        error_rate=0
                    )
                
                # Add operation to service
                self.service_dependencies.nodes[span.service_name]['operations'].add(span.operation_name)
                
                # Find parent service to create edge
                if span.parent_span_id:
                    parent_span = next(
                        (s for s in sorted_spans if s.span_id == span.parent_span_id), 
                        None
                    )
                    if parent_span and parent_span.service_name != span.service_name:
                        # Add edge with weight representing call frequency
                        if self.service_dependencies.has_edge(parent_span.service_name, span.service_name):
                            self.service_dependencies[parent_span.service_name][span.service_name]['weight'] += 1
                        else:
                            self.service_dependencies.add_edge(
                                parent_span.service_name, 
                                span.service_name, 
                                weight=1,
                                avg_latency=span.duration_ms
                            )
    
    def _analyze_performance_patterns(self, traces: List[Trace]) -> Dict:
        """Analyze performance patterns across services"""
        
        service_metrics = defaultdict(lambda: {
            'latencies': [],
            'error_rates': [],
            'throughput': 0,
            'p95_latency': 0,
            'p99_latency': 0
        })
        
        # Collect metrics per service
        for trace in traces:
            for span in trace.spans:
                service_metrics[span.service_name]['latencies'].append(span.duration_ms)
                if span.status == 'error':
                    service_metrics[span.service_name]['error_rates'].append(1)
                else:
                    service_metrics[span.service_name]['error_rates'].append(0)
        
        # Calculate statistics
        performance_insights = {}
        for service, metrics in service_metrics.items():
            latencies = np.array(metrics['latencies'])
            error_rates = np.array(metrics['error_rates'])
            
            if len(latencies) > 0:
                performance_insights[service] = {
                    'avg_latency_ms': float(np.mean(latencies)),
                    'p95_latency_ms': float(np.percentile(latencies, 95)),
                    'p99_latency_ms': float(np.percentile(latencies, 99)),
                    'error_rate': float(np.mean(error_rates)),
                    'throughput_rps': len(latencies) / 3600,  # Assuming 1 hour window
                    'latency_trend': self._calculate_trend(latencies),
                    'performance_score': self._calculate_performance_score(latencies, error_rates)
                }
        
        return performance_insights
    
    def _detect_trace_anomalies(self, traces: List[Trace]) -> Dict:
        """Detect anomalous traces using statistical analysis"""
        
        # Extract trace-level features
        trace_features = []
        for trace in traces:
            features = {
                'total_duration': trace.total_duration_ms,
                'service_count': trace.service_count,
                'error_count': trace.error_count,
                'span_count': len(trace.spans),
                'max_depth': self._calculate_trace_depth(trace),
                'critical_path_length': len(trace.critical_path)
            }
            trace_features.append((trace.trace_id, features))
        
        # Detect anomalies using statistical thresholds
        anomalous_traces = []
        
        # Extract just the feature values for statistical analysis
        durations = [f[1]['total_duration'] for f in trace_features]
        service_counts = [f[1]['service_count'] for f in trace_features]
        
        if durations:
            duration_mean = np.mean(durations)
            duration_std = np.std(durations)
            duration_threshold = duration_mean + 2 * duration_std
            
            service_mean = np.mean(service_counts)
            service_std = np.std(service_counts)
            service_threshold = service_mean + 2 * service_std
            
            for trace_id, features in trace_features:
                anomaly_reasons = []
                
                if features['total_duration'] > duration_threshold:
                    anomaly_reasons.append(f"High latency: {features['total_duration']:.1f}ms")
                
                if features['service_count'] > service_threshold:
                    anomaly_reasons.append(f"Too many services: {features['service_count']}")
                
                if features['error_count'] > 0:
                    anomaly_reasons.append(f"Contains errors: {features['error_count']}")
                
                if anomaly_reasons:
                    anomalous_traces.append({
                        'trace_id': trace_id,
                        'anomaly_score': len(anomaly_reasons),
                        'reasons': anomaly_reasons,
                        'features': features
                    })
        
        return {
            'anomalous_traces': sorted(anomalous_traces, key=lambda x: x['anomaly_score'], reverse=True),
            'anomaly_rate': len(anomalous_traces) / len(traces) if traces else 0,
            'common_anomaly_patterns': self._identify_common_anomaly_patterns(anomalous_traces)
        }
    
    def _identify_service_bottlenecks(self, traces: List[Trace]) -> Dict:
        """Identify service bottlenecks from trace analysis"""
        
        service_performance = defaultdict(lambda: {
            'total_time': 0,
            'call_count': 0,
            'critical_path_appearances': 0,
            'downstream_impact': 0
        })
        
        for trace in traces:
            # Identify critical path (longest duration chain)
            critical_path = self._find_critical_path(trace)
            
            for span in trace.spans:
                service = span.service_name
                service_performance[service]['total_time'] += span.duration_ms
                service_performance[service]['call_count'] += 1
                
                if service in critical_path:
                    service_performance[service]['critical_path_appearances'] += 1
        
        # Calculate bottleneck scores
        bottlenecks = []
        for service, perf in service_performance.items():
            if perf['call_count'] > 0:
                avg_latency = perf['total_time'] / perf['call_count']
                critical_path_ratio = perf['critical_path_appearances'] / perf['call_count']
                
                # Calculate bottleneck score
                bottleneck_score = (avg_latency * 0.4) + (critical_path_ratio * 60)
                
                if bottleneck_score > 50:  # Threshold for bottleneck identification
                    bottlenecks.append({
                        'service': service,
                        'bottleneck_score': bottleneck_score,
                        'avg_latency_ms': avg_latency,
                        'critical_path_ratio': critical_path_ratio,
                        'call_frequency': perf['call_count'],
                        'impact_level': 'high' if bottleneck_score > 100 else 'medium'
                    })
        
        return {
            'identified_bottlenecks': sorted(bottlenecks, key=lambda x: x['bottleneck_score'], reverse=True),
            'bottleneck_count': len(bottlenecks),
            'system_bottleneck_ratio': len(bottlenecks) / len(service_performance) if service_performance else 0
        }
    
    def _analyze_error_propagation(self, traces: List[Trace]) -> Dict:
        """Analyze how errors propagate through the system"""
        
        error_propagation_patterns = []
        service_error_rates = defaultdict(lambda: {'errors': 0, 'total': 0})
        
        for trace in traces:
            error_chain = []
            
            # Sort spans by start time to track error propagation
            sorted_spans = sorted(trace.spans, key=lambda s: s.start_time)
            
            for span in sorted_spans:
                service_error_rates[span.service_name]['total'] += 1
                
                if span.status == 'error':
                    service_error_rates[span.service_name]['errors'] += 1
                    error_chain.append({
                        'service': span.service_name,
                        'operation': span.operation_name,
                        'timestamp': span.start_time,
                        'error_type': span.tags.get('error.type', 'unknown')
                    })
            
            if len(error_chain) > 1:
                error_propagation_patterns.append({
                    'trace_id': trace.trace_id,
                    'error_chain': error_chain,
                    'propagation_speed_ms': (error_chain[-1]['timestamp'] - error_chain[0]['timestamp']).total_seconds() * 1000
                })
        
        # Calculate error rates per service
        error_rates = {}
        for service, counts in service_error_rates.items():
            error_rates[service] = {
                'error_rate': counts['errors'] / counts['total'] if counts['total'] > 0 else 0,
                'total_requests': counts['total'],
                'error_count': counts['errors']
            }
        
        return {
            'error_propagation_patterns': error_propagation_patterns,
            'service_error_rates': error_rates,
            'most_error_prone_services': sorted(
                error_rates.items(), 
                key=lambda x: x[1]['error_rate'], 
                reverse=True
            )[:5]
        }
    
    def _find_critical_path(self, trace: Trace) -> List[str]:
        """Find the critical path (longest duration chain) in a trace"""
        
        # Build span dependency graph
        span_graph = nx.DiGraph()
        span_map = {span.span_id: span for span in trace.spans}
        
        for span in trace.spans:
            span_graph.add_node(span.span_id, duration=span.duration_ms, service=span.service_name)
            
            if span.parent_span_id and span.parent_span_id in span_map:
                span_graph.add_edge(span.parent_span_id, span.span_id)
        
        # Find longest path by duration
        longest_path = []
        max_duration = 0
        
        # Get all root nodes (no incoming edges)
        root_nodes = [node for node in span_graph.nodes() if span_graph.in_degree(node) == 0]
        
        for root in root_nodes:
            paths = list(nx.all_simple_paths(span_graph, root, 
                                           [node for node in span_graph.nodes() 
                                            if span_graph.out_degree(node) == 0]))
            
            for path in paths:
                path_duration = sum(span_graph.nodes[span_id]['duration'] for span_id in path)
                if path_duration > max_duration:
                    max_duration = path_duration
                    longest_path = [span_graph.nodes[span_id]['service'] for span_id in path]
        
        return longest_path
    
    def _calculate_trace_depth(self, trace: Trace) -> int:
        """Calculate the maximum depth of a trace"""
        depth_map = {}
        
        # Sort spans to process parents before children
        sorted_spans = sorted(trace.spans, key=lambda s: s.start_time)
        
        for span in sorted_spans:
            if span.parent_span_id is None:
                depth_map[span.span_id] = 1
            else:
                parent_depth = depth_map.get(span.parent_span_id, 0)
                depth_map[span.span_id] = parent_depth + 1
        
        return max(depth_map.values()) if depth_map else 0
    
    def _calculate_trend(self, values: np.ndarray) -> str:
        """Calculate trend direction for a series of values"""
        if len(values) < 2:
            return "stable"
        
        # Simple linear regression to determine trend
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_performance_score(self, latencies: np.ndarray, error_rates: np.ndarray) -> float:
        """Calculate overall performance score (0-100)"""
        if len(latencies) == 0:
            return 0
        
        # Latency score (lower is better)
        avg_latency = np.mean(latencies)
        latency_score = max(0, 100 - (avg_latency / 10))  # 1000ms = 0 score
        
        # Error rate score (lower is better)
        avg_error_rate = np.mean(error_rates)
        error_score = max(0, 100 - (avg_error_rate * 100))
        
        return (latency_score * 0.7) + (error_score * 0.3)
    
    def _identify_common_anomaly_patterns(self, anomalous_traces: List[Dict]) -> List[Dict]:
        """Identify common patterns in anomalous traces"""
        patterns = []
        
        # Group by similar anomaly reasons
        reason_groups = defaultdict(list)
        for trace in anomalous_traces:
            reason_key = tuple(sorted(trace['reasons']))
            reason_groups[reason_key].append(trace)
        
        for reasons, traces in reason_groups.items():
            if len(traces) >= 2:  # Pattern needs at least 2 occurrences
                patterns.append({
                    'pattern_type': reasons,
                    'occurrence_count': len(traces),
                    'avg_anomaly_score': np.mean([t['anomaly_score'] for t in traces]),
                    'affected_traces': [t['trace_id'] for t in traces]
                })
        
        return sorted(patterns, key=lambda x: x['occurrence_count'], reverse=True)
    
    def _export_service_topology(self) -> Dict:
        """Export service topology information"""
        return {
            'service_count': self.service_dependencies.number_of_nodes(),
            'dependency_count': self.service_dependencies.number_of_edges(),
            'services': list(self.service_dependencies.nodes()),
            'dependencies': [
                {
                    'from': edge[0],
                    'to': edge[1],
                    'weight': self.service_dependencies[edge[0]][edge[1]].get('weight', 1)
                }
                for edge in self.service_dependencies.edges()
            ],
            'critical_services': self._identify_critical_services()
        }
    
    def _identify_critical_services(self) -> List[str]:
        """Identify critical services based on centrality measures"""
        try:
            centrality = nx.betweenness_centrality(self.service_dependencies)
            sorted_services = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
            return [service for service, score in sorted_services[:5] if score > 0.1]
        except:
            return []
    
    def _generate_optimization_recommendations(self, performance_analysis: Dict, bottleneck_analysis: Dict) -> List[Dict]:
        """Generate optimization recommendations based on analysis"""
        recommendations = []
        
        # Performance-based recommendations
        for service, metrics in performance_analysis.items():
            if metrics['p95_latency_ms'] > 1000:
                recommendations.append({
                    'type': 'performance_optimization',
                    'service': service,
                    'issue': 'High P95 latency',
                    'recommendation': 'Optimize slow operations or scale service',
                    'priority': 'high',
                    'estimated_impact': 'Reduce latency by 30-50%'
                })
            
            if metrics['error_rate'] > 0.05:
                recommendations.append({
                    'type': 'reliability_improvement',
                    'service': service,
                    'issue': 'High error rate',
                    'recommendation': 'Implement better error handling and retry logic',
                    'priority': 'critical',
                    'estimated_impact': 'Reduce error rate by 70-90%'
                })
        
        # Bottleneck-based recommendations
        for bottleneck in bottleneck_analysis.get('identified_bottlenecks', []):
            recommendations.append({
                'type': 'bottleneck_resolution',
                'service': bottleneck['service'],
                'issue': f"Service bottleneck (score: {bottleneck['bottleneck_score']:.1f})",
                'recommendation': 'Scale horizontally or optimize critical operations',
                'priority': bottleneck['impact_level'],
                'estimated_impact': 'Improve overall system throughput by 20-40%'
            })
        
        return sorted(recommendations, key=lambda x: {'critical': 0, 'high': 1, 'medium': 2}.get(x['priority'], 3))