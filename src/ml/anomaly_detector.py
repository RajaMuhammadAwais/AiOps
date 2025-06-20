"""
Machine Learning based anomaly detection for AIOps
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from prophet import Prophet
from typing import List, Dict, Tuple, Optional
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """ML-based anomaly detection system"""
    
    def __init__(self):
        self.isolation_forest = IsolationForest(contamination='auto', random_state=42)
        self.scaler = StandardScaler()
        self.prophet_models = {}  # Store Prophet models per metric
        self.baseline_data = {}
        self.is_trained = False
        
    def train_baseline(self, metrics_data: List[Dict]) -> None:
        """Train baseline models on historical metrics"""
        try:
            df = pd.DataFrame(metrics_data)
            if df.empty:
                logger.warning("No data provided for training baseline")
                return
                
            # Prepare features for isolation forest
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 0:
                X = df[numeric_columns].fillna(0)
                X_scaled = self.scaler.fit_transform(X)
                self.isolation_forest.fit(X_scaled)
                self.is_trained = True
                logger.info(f"Trained anomaly detector on {len(df)} samples")
            
            # Train Prophet models for time series forecasting
            self._train_prophet_models(df)
            
        except Exception as e:
            logger.error(f"Error training baseline: {e}")
    
    def _train_prophet_models(self, df: pd.DataFrame) -> None:
        """Train Prophet models for time series forecasting"""
        try:
            if 'timestamp' not in df.columns:
                return
                
            # Group by metric name and train individual models
            if 'name' in df.columns:
                for metric_name in df['name'].unique():
                    metric_data = df[df['name'] == metric_name].copy()
                    if len(metric_data) < 10:  # Need minimum data points
                        continue
                        
                    # Prepare data for Prophet
                    prophet_df = pd.DataFrame({
                        'ds': pd.to_datetime(metric_data['timestamp']),
                        'y': metric_data.get('value', 0)
                    })
                    
                    model = Prophet(
                        changepoint_prior_scale=0.05,
                        seasonality_prior_scale=10
                    )
                    model.fit(prophet_df)
                    self.prophet_models[metric_name] = model
                
            logger.info(f"Trained Prophet models for {len(self.prophet_models)} metrics")
            
        except Exception as e:
            logger.error(f"Error training Prophet models: {e}")
    
    def detect_anomalies(self, current_metrics: List[Dict]) -> List[Dict]:
        """Detect anomalies in current metrics"""
        anomalies = []
        
        try:
            if not self.is_trained:
                logger.warning("Anomaly detector not trained")
                return anomalies
                
            df = pd.DataFrame(current_metrics)
            if df.empty:
                return anomalies
            
            # Isolation Forest detection
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 0:
                X = df[numeric_columns].fillna(0)
                X_scaled = self.scaler.transform(X)
                anomaly_scores = self.isolation_forest.decision_function(X_scaled)
                is_anomaly = self.isolation_forest.predict(X_scaled) == -1
                
                for idx, (is_anom, score) in enumerate(zip(is_anomaly, anomaly_scores)):
                    if is_anom:
                        anomaly = {
                            'type': 'isolation_forest',
                            'metric_index': idx,
                            'anomaly_score': float(score),
                            'timestamp': datetime.now(),
                            'data': current_metrics[idx] if idx < len(current_metrics) else {}
                        }
                        anomalies.append(anomaly)
            
            # Prophet-based anomaly detection
            prophet_anomalies = self._detect_prophet_anomalies(current_metrics)
            anomalies.extend(prophet_anomalies)
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            
        return anomalies
    
    def _detect_prophet_anomalies(self, metrics: List[Dict]) -> List[Dict]:
        """Detect anomalies using Prophet forecasting"""
        anomalies = []
        
        try:
            for metric in metrics:
                metric_name = metric.get('name')
                if metric_name not in self.prophet_models:
                    continue
                    
                model = self.prophet_models[metric_name]
                current_time = datetime.now()
                
                # Create future dataframe for prediction
                future_df = pd.DataFrame({'ds': [current_time]})
                forecast = model.predict(future_df)
                
                predicted_value = forecast['yhat'].iloc[0]
                upper_bound = forecast['yhat_upper'].iloc[0]
                lower_bound = forecast['yhat_lower'].iloc[0]
                actual_value = metric.get('value', 0)
                
                # Check if actual value is outside prediction interval
                if actual_value > upper_bound or actual_value < lower_bound:
                    deviation = abs(actual_value - predicted_value) / max(abs(predicted_value), 1)
                    
                    anomaly = {
                        'type': 'prophet_forecast',
                        'metric_name': metric_name,
                        'actual_value': actual_value,
                        'predicted_value': predicted_value,
                        'upper_bound': upper_bound,
                        'lower_bound': lower_bound,
                        'deviation_ratio': deviation,
                        'timestamp': current_time,
                        'data': metric
                    }
                    anomalies.append(anomaly)
                    
        except Exception as e:
            logger.error(f"Error in Prophet anomaly detection: {e}")
            
        return anomalies
    
    def cluster_anomalies(self, anomalies: List[Dict]) -> List[List[Dict]]:
        """Cluster related anomalies together"""
        if len(anomalies) < 2:
            return [anomalies] if anomalies else []
            
        try:
            # Extract features for clustering
            features = []
            for anomaly in anomalies:
                feature_vector = [
                    anomaly.get('anomaly_score', 0),
                    hash(anomaly.get('metric_name', '')) % 1000,  # Simple hash for metric name
                    anomaly.get('deviation_ratio', 0)
                ]
                features.append(feature_vector)
            
            features_array = np.array(features)
            
            # Use DBSCAN for clustering
            clustering = DBSCAN(eps=0.5, min_samples=2)
            cluster_labels = clustering.fit_predict(features_array)
            
            # Group anomalies by cluster
            clusters = {}
            for idx, label in enumerate(cluster_labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(anomalies[idx])
            
            return list(clusters.values())
            
        except Exception as e:
            logger.error(f"Error clustering anomalies: {e}")
            return [anomalies]
    
    def predict_incident_severity(self, anomalies: List[Dict], metrics_context: Dict) -> str:
        """Predict incident severity based on anomalies and context"""
        try:
            if not anomalies:
                return "low"
            
            # Calculate severity score based on multiple factors
            severity_score = 0
            
            # Factor 1: Number of anomalies
            severity_score += min(len(anomalies) * 10, 40)
            
            # Factor 2: Anomaly scores
            avg_anomaly_score = np.mean([abs(a.get('anomaly_score', 0)) for a in anomalies])
            severity_score += avg_anomaly_score * 20
            
            # Factor 3: Affected services/systems
            affected_services = set()
            for anomaly in anomalies:
                service = anomaly.get('data', {}).get('service', 'unknown')
                affected_services.add(service)
            severity_score += len(affected_services) * 5
            
            # Factor 4: System resource anomalies (CPU, memory, etc.)
            critical_metrics = ['cpu_usage', 'memory_usage', 'disk_usage', 'error_rate']
            for anomaly in anomalies:
                metric_name = anomaly.get('metric_name', '').lower()
                if any(critical in metric_name for critical in critical_metrics):
                    severity_score += 15
            
            # Convert score to severity level
            if severity_score >= 80:
                return "critical"
            elif severity_score >= 60:
                return "high"
            elif severity_score >= 30:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            logger.error(f"Error predicting incident severity: {e}")
            return "medium"  # Default to medium severity
    
    def get_model_info(self) -> Dict:
        """Get information about trained models"""
        return {
            'is_trained': self.is_trained,
            'prophet_models': list(self.prophet_models.keys()),
            'model_type': 'IsolationForest + Prophet',
            'contamination_rate': 0.1
        }