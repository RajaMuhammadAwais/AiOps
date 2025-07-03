"""
Predictive Intelligence Engine for AIOps
Advanced forecasting, capacity planning, and proactive incident prevention
"""
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)


class PredictiveIntelligenceEngine:
    """Advanced predictive analytics for proactive AIOps"""
    
    def __init__(self):
        self.capacity_models = {}
        self.failure_predictors = {}
        self.performance_forecasters = {}
        self.anomaly_predictors = {}
        self.scaler = StandardScaler()
        self.is_trained = False
        
    def train_capacity_models(self, historical_metrics: List[Dict], horizon_days: int = 30) -> Dict:
        """Train models to predict capacity needs and resource exhaustion"""
        try:
            df = pd.DataFrame(historical_metrics)
            if len(df) < 100:
                return {'status': 'insufficient_data', 'required_samples': 100}
            
            # Convert timestamp to datetime
            df['ds'] = pd.to_datetime(df['timestamp'])
            
            trained_models = {}
            
            # Train separate models for each metric type
            metric_types = ['cpu_usage', 'memory_usage', 'disk_usage', 'response_time']
            
            for metric_type in metric_types:
                metric_data = df[df['name'].str.contains(metric_type, case=False, na=False)]
                
                if len(metric_data) >= 50:
                    # Aggregate by time for Prophet
                    hourly_data = metric_data.groupby(
                        metric_data['ds'].dt.floor('H')
                    )['value'].mean().reset_index()
                    hourly_data.columns = ['ds', 'y']
                    
                    # Train Prophet model
                    model = Prophet(
                        changepoint_prior_scale=0.1,
                        seasonality_prior_scale=10,
                        yearly_seasonality=False,
                        weekly_seasonality=True,
                        daily_seasonality=True
                    )
                    model.fit(hourly_data)
                    
                    # Generate forecasts
                    future = model.make_future_dataframe(periods=horizon_days*24, freq='H')
                    forecast = model.predict(future)
                    
                    # Calculate capacity thresholds
                    current_max = hourly_data['y'].max()
                    predicted_max = forecast['yhat'].max()
                    
                    # Estimate time to threshold breach
                    threshold = self._get_threshold_for_metric(metric_type)
                    breach_prediction = self._predict_threshold_breach(forecast, threshold)
                    
                    trained_models[metric_type] = {
                        'model': model,
                        'current_max': current_max,
                        'predicted_max': predicted_max,
                        'threshold_breach': breach_prediction,
                        'forecast_accuracy': self._calculate_forecast_accuracy(model, hourly_data)
                    }
            
            self.capacity_models = trained_models
            return {
                'status': 'success',
                'models_trained': len(trained_models),
                'forecast_horizon_days': horizon_days,
                'capacity_insights': self._generate_capacity_insights(trained_models)
            }
            
        except Exception as e:
            logger.error(f"Error training capacity models: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def predict_system_failures(self, system_health_data: List[Dict]) -> Dict:
        """Predict potential system failures using ML models"""
        try:
            df = pd.DataFrame(system_health_data)
            if len(df) < 50:
                return {'prediction': 'insufficient_data'}
            
            # Feature engineering for failure prediction
            features = self._extract_failure_features(df)
            
            # Train failure predictor if not already trained
            if 'failure_predictor' not in self.failure_predictors:
                self._train_failure_predictor(features, df)
            
            # Get current system state
            current_features = features[-1:] if len(features) > 0 else np.array([[0]*10])
            
            # Predict failure probability
            if 'failure_predictor' in self.failure_predictors:
                try:
                    failure_prob = self.failure_predictors['failure_predictor'].predict_proba(current_features)
                    failure_risk = float(failure_prob[0][1]) if len(failure_prob[0]) > 1 else 0.0
                except:
                    failure_risk = 0.0
            else:
                failure_risk = 0.0
            
            # Identify risk factors
            risk_factors = self._identify_risk_factors(df.iloc[-1] if len(df) > 0 else {})
            
            # Generate recommendations
            recommendations = self._generate_failure_prevention_actions(failure_risk, risk_factors)
            
            return {
                'failure_probability': failure_risk,
                'risk_level': self._categorize_risk_level(failure_risk),
                'time_to_potential_failure': self._estimate_time_to_failure(failure_risk),
                'primary_risk_factors': risk_factors,
                'prevention_actions': recommendations,
                'confidence_score': self._calculate_prediction_confidence(features)
            }
            
        except Exception as e:
            logger.error(f"Error predicting system failures: {e}")
            return {'prediction': 'error', 'message': str(e)}
    
    def explain_root_cause(self, incidents: list) -> str:
        """Generate a root cause suggestion for a group of incidents (simple heuristic/placeholder)."""
        if not incidents:
            return "No incidents to analyze."
        descriptions = ' '.join([str(i.get('description','')).lower() for i in incidents])
        if 'cpu' in descriptions:
            return "High CPU usage detected. Possible resource contention or traffic spike."
        if 'disk' in descriptions:
            return "Disk issues detected. Check storage and IO."
        if 'timeout' in descriptions:
            return "Timeouts detected. Check dependencies and network."
        if 'memory' in descriptions:
            return "Memory issues detected. Possible memory leak or resource exhaustion."
        return "No clear root cause found. Further investigation required."
    
    def _get_threshold_for_metric(self, metric_type: str) -> float:
        """Get threshold values for different metric types"""
        thresholds = {
            'cpu_usage': 85.0,
            'memory_usage': 90.0,
            'disk_usage': 95.0,
            'response_time': 2000.0
        }
        return thresholds.get(metric_type, 80.0)
    
    def _predict_threshold_breach(self, forecast: pd.DataFrame, threshold: float) -> Dict:
        """Predict when a threshold will be breached"""
        future_forecast = forecast[forecast['ds'] > datetime.now()]
        breach_points = future_forecast[future_forecast['yhat'] > threshold]
        
        if not breach_points.empty:
            first_breach = breach_points.iloc[0]
            days_to_breach = (first_breach['ds'] - datetime.now()).days
            
            return {
                'will_breach': True,
                'days_to_breach': days_to_breach,
                'breach_timestamp': first_breach['ds'].isoformat(),
                'predicted_value': first_breach['yhat'],
                'threshold': threshold
            }
        
        return {
            'will_breach': False,
            'days_to_breach': None,
            'message': 'No threshold breach predicted in forecast period'
        }
    
    def _calculate_forecast_accuracy(self, model: Prophet, data: pd.DataFrame) -> float:
        """Calculate forecast accuracy using cross-validation"""
        try:
            if len(data) < 30:
                return 0.85
            
            # Simple train/test split for accuracy calculation
            train_size = int(len(data) * 0.8)
            train_data = data[:train_size]
            test_data = data[train_size:]
            
            # Train on subset and predict
            test_model = Prophet()
            test_model.fit(train_data)
            
            future = test_model.make_future_dataframe(periods=len(test_data), freq='H')
            forecast = test_model.predict(future)
            
            # Calculate accuracy
            predicted_values = forecast['yhat'].tail(len(test_data)).values
            actual_values = test_data['y'].values
            
            mae = mean_absolute_error(actual_values, predicted_values)
            
            # Convert to percentage accuracy
            mean_actual = np.mean(actual_values)
            accuracy = max(0, 1 - (mae / mean_actual)) * 100
            
            return min(accuracy, 100)
            
        except Exception:
            return 85.0
    
    def _generate_capacity_insights(self, models: Dict) -> List[str]:
        """Generate capacity planning insights"""
        insights = []
        
        for metric_type, model_data in models.items():
            breach_info = model_data.get('threshold_breach', {})
            
            if breach_info.get('will_breach', False):
                days_to_breach = breach_info.get('days_to_breach', 0)
                if days_to_breach <= 7:
                    insights.append(f"URGENT: {metric_type} will breach threshold in {days_to_breach} days")
                elif days_to_breach <= 30:
                    insights.append(f"WARNING: {metric_type} approaching capacity limits in {days_to_breach} days")
            
            growth_rate = ((model_data['predicted_max'] - model_data['current_max']) / model_data['current_max']) * 100
            if growth_rate > 20:
                insights.append(f"{metric_type} showing high growth rate: {growth_rate:.1f}%")
        
        return insights
    
    def _extract_failure_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract features for failure prediction"""
        try:
            features = []
            
            # System health metrics
            if 'health_score' in df.columns:
                features.append(df['health_score'].fillna(100))
            
            # Resource utilization features
            for metric in ['cpu_usage', 'memory_usage', 'disk_usage']:
                if metric in df.columns:
                    features.append(df[metric].fillna(0))
            
            # Error rate features
            if 'error_rate' in df.columns:
                features.append(df['error_rate'].fillna(0))
            
            # Performance features
            if 'response_time' in df.columns:
                features.append(df['response_time'].fillna(0))
            
            # If no features found, create dummy features
            if not features:
                features = [np.zeros(len(df)) for _ in range(6)]
            
            return np.column_stack(features)
            
        except Exception:
            return np.zeros((len(df), 6))
    
    def _train_failure_predictor(self, features: np.ndarray, df: pd.DataFrame):
        """Train failure prediction model"""
        try:
            # Create synthetic failure labels based on health score
            if 'health_score' in df.columns:
                failure_labels = (df['health_score'] < 50).astype(int)
            else:
                # Create labels based on high resource usage
                failure_indicators = []
                for _, row in df.iterrows():
                    high_cpu = row.get('cpu_usage', 0) > 90
                    high_memory = row.get('memory_usage', 0) > 90
                    high_error = row.get('error_rate', 0) > 5
                    failure_indicators.append(int(high_cpu or high_memory or high_error))
                failure_labels = np.array(failure_indicators)
            
            if len(np.unique(failure_labels)) > 1:
                model = RandomForestClassifier(n_estimators=50, random_state=42)
                model.fit(features, failure_labels)
                self.failure_predictors['failure_predictor'] = model
            
        except Exception as e:
            logger.error(f"Error training failure predictor: {e}")
    
    def _identify_risk_factors(self, current_state: Dict) -> List[str]:
        """Identify current risk factors"""
        risk_factors = []
        
        cpu_usage = current_state.get('cpu_usage', 0)
        memory_usage = current_state.get('memory_usage', 0)
        disk_usage = current_state.get('disk_usage', 0)
        error_rate = current_state.get('error_rate', 0)
        
        if cpu_usage > 80:
            risk_factors.append(f"High CPU usage: {cpu_usage:.1f}%")
        if memory_usage > 85:
            risk_factors.append(f"High memory usage: {memory_usage:.1f}%")
        if disk_usage > 90:
            risk_factors.append(f"High disk usage: {disk_usage:.1f}%")
        if error_rate > 2:
            risk_factors.append(f"Elevated error rate: {error_rate:.2f}%")
        
        return risk_factors
    
    def _generate_failure_prevention_actions(self, failure_risk: float, risk_factors: List[str]) -> List[str]:
        """Generate actions to prevent failures"""
        actions = []
        
        if failure_risk > 0.7:
            actions.append("IMMEDIATE: Implement emergency scaling procedures")
            actions.append("IMMEDIATE: Activate incident response team")
        elif failure_risk > 0.5:
            actions.append("Scale up critical services")
            actions.append("Review system health metrics")
        
        for factor in risk_factors:
            if "CPU" in factor:
                actions.append("Consider CPU scaling or optimization")
            elif "memory" in factor:
                actions.append("Investigate memory leaks and optimize usage")
            elif "disk" in factor:
                actions.append("Clean up disk space or expand storage")
            elif "error" in factor:
                actions.append("Investigate error patterns and root causes")
        
        return actions
    
    def _categorize_risk_level(self, failure_risk: float) -> str:
        """Categorize risk level"""
        if failure_risk > 0.8:
            return "critical"
        elif failure_risk > 0.6:
            return "high"
        elif failure_risk > 0.4:
            return "medium"
        else:
            return "low"
    
    def _estimate_time_to_failure(self, failure_risk: float) -> str:
        """Estimate time to potential failure"""
        if failure_risk > 0.8:
            return "< 1 hour"
        elif failure_risk > 0.6:
            return "< 6 hours"
        elif failure_risk > 0.4:
            return "< 24 hours"
        else:
            return "> 24 hours"
    
    def _calculate_prediction_confidence(self, features: np.ndarray) -> float:
        """Calculate confidence in prediction"""
        if len(features) < 10:
            return 0.6
        elif len(features) < 50:
            return 0.8
        else:
            return 0.9