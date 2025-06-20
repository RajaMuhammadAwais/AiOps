"""
Alert correlation and noise reduction using ML techniques
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertCorrelator:
    """ML-based alert correlation and noise reduction"""
    
    def __init__(self, similarity_threshold=0.7, time_window_minutes=15):
        self.similarity_threshold = similarity_threshold
        self.time_window = timedelta(minutes=time_window_minutes)
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.alert_history = []
        self.suppressed_patterns = set()
        
    def correlate_alerts(self, alerts: List[Dict]) -> Dict:
        """Correlate alerts and identify duplicates/noise"""
        if not alerts:
            return {"correlated_groups": [], "suppressed_alerts": [], "unique_alerts": []}
        
        # Group alerts by time proximity
        time_groups = self._group_by_time(alerts)
        
        correlated_groups = []
        suppressed_alerts = []
        unique_alerts = []
        
        for time_group in time_groups:
            if len(time_group) == 1:
                unique_alerts.extend(time_group)
                continue
                
            # Find similar alerts within the time group
            similarity_groups = self._find_similar_alerts(time_group)
            
            for group in similarity_groups:
                if len(group) > 1:
                    # Mark as correlated group
                    primary_alert = self._select_primary_alert(group)
                    secondary_alerts = [a for a in group if a['id'] != primary_alert['id']]
                    
                    correlated_groups.append({
                        'primary_alert': primary_alert,
                        'correlated_alerts': secondary_alerts,
                        'correlation_score': self._calculate_group_score(group),
                        'pattern': self._extract_pattern(group)
                    })
                    
                    # Check if this should be suppressed due to noise
                    if self._is_noise_pattern(group):
                        suppressed_alerts.extend(secondary_alerts)
                    else:
                        unique_alerts.append(primary_alert)
                else:
                    unique_alerts.extend(group)
        
        return {
            "correlated_groups": correlated_groups,
            "suppressed_alerts": suppressed_alerts,
            "unique_alerts": unique_alerts,
            "noise_reduction_ratio": len(suppressed_alerts) / len(alerts) if alerts else 0
        }
    
    def _group_by_time(self, alerts: List[Dict]) -> List[List[Dict]]:
        """Group alerts by time proximity"""
        if not alerts:
            return []
            
        # Sort alerts by timestamp
        sorted_alerts = sorted(alerts, key=lambda x: x.get('timestamp', datetime.now()))
        
        groups = []
        current_group = [sorted_alerts[0]]
        
        for alert in sorted_alerts[1:]:
            last_alert_time = current_group[-1].get('timestamp', datetime.now())
            current_alert_time = alert.get('timestamp', datetime.now())
            
            if isinstance(last_alert_time, str):
                last_alert_time = datetime.fromisoformat(last_alert_time.replace('Z', '+00:00'))
            if isinstance(current_alert_time, str):
                current_alert_time = datetime.fromisoformat(current_alert_time.replace('Z', '+00:00'))
            
            if current_alert_time - last_alert_time <= self.time_window:
                current_group.append(alert)
            else:
                groups.append(current_group)
                current_group = [alert]
        
        groups.append(current_group)
        return [group for group in groups if group]  # Filter empty groups
    
    def _find_similar_alerts(self, alerts: List[Dict]) -> List[List[Dict]]:
        """Find similar alerts using text similarity and other features"""
        if len(alerts) < 2:
            return [alerts]
        
        try:
            # Extract text features for similarity comparison
            alert_texts = []
            for alert in alerts:
                text_parts = [
                    alert.get('name', ''),
                    alert.get('message', ''),
                    ' '.join([f"{k}:{v}" for k, v in alert.get('labels', {}).items()])
                ]
                alert_texts.append(' '.join(text_parts))
            
            # Calculate TF-IDF similarity
            if not alert_texts or all(not text.strip() for text in alert_texts):
                return [alerts]  # Return all as one group if no text content
                
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(alert_texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Use DBSCAN clustering based on similarity
            distance_matrix = 1 - similarity_matrix
            clustering = DBSCAN(eps=1-self.similarity_threshold, min_samples=1, metric='precomputed')
            cluster_labels = clustering.fit_predict(distance_matrix)
            
            # Group alerts by cluster
            clusters = defaultdict(list)
            for idx, label in enumerate(cluster_labels):
                clusters[label].append(alerts[idx])
            
            return list(clusters.values())
            
        except Exception as e:
            logger.error(f"Error finding similar alerts: {e}")
            return [alerts]
    
    def _select_primary_alert(self, alert_group: List[Dict]) -> Dict:
        """Select the primary alert from a correlated group"""
        # Prioritize by severity, then by timestamp
        severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        
        def alert_priority(alert):
            severity_score = severity_order.get(alert.get('severity', 'low'), 1)
            timestamp = alert.get('timestamp', datetime.now())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            # Earlier alerts get higher priority (negative timestamp for sorting)
            return (severity_score, -timestamp.timestamp())
        
        return max(alert_group, key=alert_priority)
    
    def _calculate_group_score(self, alert_group: List[Dict]) -> float:
        """Calculate correlation score for an alert group"""
        if len(alert_group) < 2:
            return 0.0
        
        # Factor in group size, severity, and time clustering
        size_score = min(len(alert_group) / 10, 1.0)  # Normalize to 0-1
        
        # Severity correlation score
        severities = [alert.get('severity', 'low') for alert in alert_group]
        unique_severities = set(severities)
        severity_score = 1.0 - (len(unique_severities) / 4)  # More uniform = higher score
        
        # Time clustering score (how close in time)
        timestamps = []
        for alert in alert_group:
            ts = alert.get('timestamp', datetime.now())
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            timestamps.append(ts)
        
        if len(timestamps) > 1:
            time_span = (max(timestamps) - min(timestamps)).total_seconds()
            time_score = max(0, 1 - (time_span / 900))  # 15 minutes = 900 seconds
        else:
            time_score = 1.0
        
        return (size_score * 0.4 + severity_score * 0.3 + time_score * 0.3)
    
    def _extract_pattern(self, alert_group: List[Dict]) -> Dict:
        """Extract common pattern from alert group"""
        pattern = {
            'services': set(),
            'error_types': set(),
            'common_labels': {},
            'message_pattern': None
        }
        
        # Collect common attributes
        for alert in alert_group:
            # Services
            if 'service' in alert.get('labels', {}):
                pattern['services'].add(alert['labels']['service'])
            
            # Labels that appear in all alerts
            for key, value in alert.get('labels', {}).items():
                if key not in pattern['common_labels']:
                    pattern['common_labels'][key] = set()
                pattern['common_labels'][key].add(value)
        
        # Keep only labels that appear in all alerts
        all_alert_count = len(alert_group)
        pattern['common_labels'] = {
            k: v for k, v in pattern['common_labels'].items()
            if len(v) == 1  # Same value across all alerts
        }
        
        # Extract message pattern using regex
        messages = [alert.get('message', '') for alert in alert_group]
        pattern['message_pattern'] = self._find_common_message_pattern(messages)
        
        # Convert sets to lists for JSON serialization
        pattern['services'] = list(pattern['services'])
        pattern['error_types'] = list(pattern['error_types'])
        
        return pattern
    
    def _find_common_message_pattern(self, messages: List[str]) -> str:
        """Find common pattern in alert messages"""
        if not messages:
            return ""
        
        # Simple approach: find common prefixes and suffixes
        if len(messages) == 1:
            return messages[0]
        
        # Find longest common prefix
        prefix = messages[0]
        for msg in messages[1:]:
            while prefix and not msg.startswith(prefix):
                prefix = prefix[:-1]
        
        # Find longest common suffix
        suffix = messages[0]
        for msg in messages[1:]:
            while suffix and not msg.endswith(suffix):
                suffix = suffix[1:]
        
        if len(prefix) > 10:  # Meaningful prefix length
            return f"{prefix}*"
        elif len(suffix) > 10:  # Meaningful suffix length
            return f"*{suffix}"
        else:
            # Extract common keywords
            all_words = set()
            for msg in messages:
                words = re.findall(r'\w+', msg.lower())
                all_words.update(words)
            
            # Find words that appear in all messages
            common_words = []
            for word in all_words:
                if all(word in msg.lower() for msg in messages):
                    common_words.append(word)
            
            return ' '.join(common_words[:5]) if common_words else "pattern_detected"
    
    def _is_noise_pattern(self, alert_group: List[Dict]) -> bool:
        """Determine if an alert group represents noise"""
        if len(alert_group) < 3:
            return False
        
        # Check if this pattern was previously identified as noise
        pattern = self._extract_pattern(alert_group)
        pattern_signature = f"{pattern.get('message_pattern', '')}"
        
        if pattern_signature in self.suppressed_patterns:
            return True
        
        # Heuristics for noise detection
        # 1. Too many similar alerts in short time
        if len(alert_group) > 10:
            return True
        
        # 2. All alerts have very low severity
        severities = [alert.get('severity', 'low') for alert in alert_group]
        if all(sev == 'low' for sev in severities):
            return True
        
        # 3. Repetitive error messages (same service, same error repeatedly)
        services = [alert.get('labels', {}).get('service', '') for alert in alert_group]
        messages = [alert.get('message', '') for alert in alert_group]
        
        if len(set(services)) == 1 and len(set(messages)) == 1:
            # Same service, same message - likely noise if too frequent
            if len(alert_group) > 5:
                self.suppressed_patterns.add(pattern_signature)
                return True
        
        return False
    
    def learn_from_feedback(self, correlation_result: Dict, feedback: Dict):
        """Learn from human feedback to improve correlation"""
        try:
            if feedback.get('correct_correlation', True):
                # Positive feedback - reinforce current thresholds
                pass
            else:
                # Negative feedback - adjust parameters
                if feedback.get('too_aggressive'):
                    self.similarity_threshold = min(0.9, self.similarity_threshold + 0.05)
                elif feedback.get('too_conservative'):
                    self.similarity_threshold = max(0.5, self.similarity_threshold - 0.05)
            
            # Learn suppression patterns from feedback
            if feedback.get('suppress_pattern'):
                pattern = feedback.get('pattern_signature')
                if pattern:
                    self.suppressed_patterns.add(pattern)
            
            logger.info(f"Updated correlation parameters based on feedback")
            
        except Exception as e:
            logger.error(f"Error learning from feedback: {e}")
    
    def get_noise_reduction_stats(self) -> Dict:
        """Get statistics about noise reduction"""
        return {
            'suppressed_patterns': len(self.suppressed_patterns),
            'similarity_threshold': self.similarity_threshold,
            'time_window_minutes': self.time_window.total_seconds() / 60,
            'patterns': list(self.suppressed_patterns)
        }