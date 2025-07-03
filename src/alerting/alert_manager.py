"""
Alert management and self-healing actions
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import subprocess
import requests
from enum import Enum

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    ALERT_TEAM = "alert_team"
    RUN_SCRIPT = "run_script"


@dataclass
class SelfHealingAction:
    """Self-healing action definition"""
    id: str
    name: str
    action_type: ActionType
    condition: str  # Condition that triggers this action
    parameters: Dict[str, Any]
    cooldown_minutes: int = 15
    max_retries: int = 3
    enabled: bool = True


class AlertManager:
    """Manages alerts and executes self-healing actions"""
    
    def __init__(self):
        self.active_alerts = {}
        self.resolved_alerts = {}
        self.self_healing_actions = []
        self.action_history = []
        self.cooldown_tracker = {}
        
        # Initialize default self-healing actions
        self._setup_default_actions()
    
    def _setup_default_actions(self):
        """Setup default self-healing actions"""
        default_actions = [
            SelfHealingAction(
                id="restart_high_cpu_service",
                name="Restart Service on High CPU",
                action_type=ActionType.RESTART_SERVICE,
                condition="cpu_usage > 90 AND duration > 300",  # 5 minutes
                parameters={"service_patterns": ["high_cpu_service"]},
                cooldown_minutes=30
            ),
            SelfHealingAction(
                id="clear_cache_memory_high",
                name="Clear Cache on High Memory",
                action_type=ActionType.CLEAR_CACHE,
                condition="memory_usage > 85",
                parameters={"cache_types": ["redis", "memcached"]},
                cooldown_minutes=15
            ),
            SelfHealingAction(
                id="scale_on_high_load",
                name="Scale Service on High Load",
                action_type=ActionType.SCALE_SERVICE,
                condition="load_average > 5 AND response_time > 2000",
                parameters={"scale_factor": 2, "max_instances": 10},
                cooldown_minutes=10
            ),
            SelfHealingAction(
                id="alert_critical_incidents",
                name="Alert Team on Critical Issues",
                action_type=ActionType.ALERT_TEAM,
                condition="severity == 'critical'",
                parameters={"channels": ["slack", "email"], "escalation_level": 1},
                cooldown_minutes=5
            )
        ]
        
        self.self_healing_actions.extend(default_actions)
    
    async def process_alert(self, alert: Dict) -> Dict:
        """Process incoming alert and trigger actions if needed"""
        alert_id = alert.get('id')
        
        # Store alert
        self.active_alerts[alert_id] = {
            **alert,
            'received_at': datetime.now(),
            'processed': False
        }
        
        logger.info(f"Processing alert: {alert.get('name', 'Unknown')}")
        
        # Check for applicable self-healing actions
        actions_taken = []
        for action in self.self_healing_actions:
            if not action.enabled:
                continue
                
            if self._should_trigger_action(action, alert):
                result = await self._execute_action(action, alert)
                actions_taken.append({
                    'action': action.name,
                    'result': result,
                    'timestamp': datetime.now()
                })
        
        # Update alert status
        self.active_alerts[alert_id]['processed'] = True
        self.active_alerts[alert_id]['actions_taken'] = actions_taken
        
        return {
            'alert_id': alert_id,
            'processed': True,
            'actions_taken': len(actions_taken),
            'actions': actions_taken
        }
    
    def _should_trigger_action(self, action: SelfHealingAction, alert: Dict) -> bool:
        """Check if action should be triggered for this alert"""
        try:
            # Check cooldown
            if self._is_in_cooldown(action.id):
                return False
            
            # Simple condition evaluation
            # In a real system, this would be a more sophisticated rule engine
            condition = action.condition
            
            # Extract values from alert
            severity = alert.get('severity', 'low')
            cpu_usage = self._extract_metric_value(alert, 'cpu_usage')
            memory_usage = self._extract_metric_value(alert, 'memory_usage')
            load_average = self._extract_metric_value(alert, 'load_average')
            response_time = self._extract_metric_value(alert, 'response_time')
            
            # Simple condition parsing (would use a proper parser in production)
            if "severity == 'critical'" in condition and severity == 'critical':
                return True
            
            if "cpu_usage > 90" in condition and cpu_usage and cpu_usage > 90:
                return True
                
            if "memory_usage > 85" in condition and memory_usage and memory_usage > 85:
                return True
                
            if "load_average > 5" in condition and load_average and load_average > 5:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating action condition: {e}")
            return False
    
    def _extract_metric_value(self, alert: Dict, metric_name: str) -> Optional[float]:
        """Extract metric value from alert data"""
        try:
            # Check in alert metrics
            for metric in alert.get('metrics', []):
                if metric_name in metric.get('name', '').lower():
                    return float(metric.get('value', 0))
            
            # Check in alert labels
            labels = alert.get('labels', {})
            if metric_name in labels:
                return float(labels[metric_name])
            
            return None
            
        except (ValueError, TypeError):
            return None
    
    def _is_in_cooldown(self, action_id: str) -> bool:
        """Check if action is in cooldown period"""
        if action_id not in self.cooldown_tracker:
            return False
            
        last_execution = self.cooldown_tracker[action_id]
        action = next((a for a in self.self_healing_actions if a.id == action_id), None)
        
        if not action:
            return False
        
        cooldown_period = timedelta(minutes=action.cooldown_minutes)
        return datetime.now() - last_execution < cooldown_period
    
    async def _execute_action(self, action: SelfHealingAction, alert: Dict) -> Dict:
        """Execute a self-healing action"""
        try:
            logger.info(f"Executing action: {action.name}")
            
            result = {'success': False, 'message': '', 'details': {}}
            
            if action.action_type == ActionType.RESTART_SERVICE:
                result = await self._restart_service(action.parameters, alert)
            elif action.action_type == ActionType.SCALE_SERVICE:
                result = await self._scale_service(action.parameters, alert)
            elif action.action_type == ActionType.CLEAR_CACHE:
                result = await self._clear_cache(action.parameters, alert)
            elif action.action_type == ActionType.ALERT_TEAM:
                result = await self._alert_team(action.parameters, alert)
            elif action.action_type == ActionType.RUN_SCRIPT:
                result = await self._run_script(action.parameters, alert)
            else:
                result = {'success': False, 'message': f'Unknown action type: {action.action_type}'}
            
            # Record action execution
            self.action_history.append({
                'action_id': action.id,
                'action_name': action.name,
                'alert_id': alert.get('id'),
                'timestamp': datetime.now(),
                'result': result
            })
            
            # Update cooldown
            self.cooldown_tracker[action.id] = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing action {action.name}: {e}")
            return {'success': False, 'message': str(e)}
    
    async def _restart_service(self, parameters: Dict, alert: Dict) -> Dict:
        """Restart a service"""
        try:
            service_patterns = parameters.get('service_patterns', [])
            
            for pattern in service_patterns:
                # In a real system, this would integrate with service management
                # For demo, we'll simulate the action
                logger.info(f"Simulating restart of service matching pattern: {pattern}")
                
                # Simulate systemctl restart (would need proper permissions in production)
                # result = subprocess.run(['systemctl', 'restart', pattern], 
                #                        capture_output=True, text=True, timeout=30)
                
                # Simulate success for demo
                await asyncio.sleep(2)
                
            return {
                'success': True,
                'message': f'Restarted {len(service_patterns)} services',
                'details': {'services': service_patterns}
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to restart service: {e}'}
    
    async def _scale_service(self, parameters: Dict, alert: Dict) -> Dict:
        """Scale a service"""
        try:
            scale_factor = parameters.get('scale_factor', 2)
            max_instances = parameters.get('max_instances', 10)
            
            # In a real system, this would integrate with Kubernetes or container orchestration
            logger.info(f"Simulating scaling service by factor {scale_factor}")
            
            # Simulate kubectl scale deployment
            # kubectl scale deployment <deployment-name> --replicas=<new-replica-count>
            
            await asyncio.sleep(1)
            
            return {
                'success': True,
                'message': f'Scaled service by factor {scale_factor}',
                'details': {'scale_factor': scale_factor, 'max_instances': max_instances}
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to scale service: {e}'}
    
    async def _clear_cache(self, parameters: Dict, alert: Dict) -> Dict:
        """Clear cache systems"""
        try:
            cache_types = parameters.get('cache_types', [])
            cleared = []
            
            for cache_type in cache_types:
                if cache_type.lower() == 'redis':
                    # Simulate Redis FLUSHALL
                    logger.info("Simulating Redis cache clear")
                    cleared.append('redis')
                elif cache_type.lower() == 'memcached':
                    # Simulate memcached flush_all
                    logger.info("Simulating Memcached cache clear")
                    cleared.append('memcached')
            
            await asyncio.sleep(1)
            
            return {
                'success': True,
                'message': f'Cleared {len(cleared)} cache systems',
                'details': {'cleared_caches': cleared}
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to clear cache: {e}'}
    
    async def _alert_team(self, parameters: Dict, alert: Dict) -> Dict:
        """Send alert to team"""
        try:
            channels = parameters.get('channels', [])
            escalation_level = parameters.get('escalation_level', 1)
            
            # Simulate sending alerts to different channels
            sent_channels = []
            
            for channel in channels:
                if channel == 'slack':
                    # Simulate Slack webhook
                    logger.info("Simulating Slack alert")
                    sent_channels.append('slack')
                elif channel == 'email':
                    # Simulate email notification
                    logger.info("Simulating email alert")
                    sent_channels.append('email')
            
            await asyncio.sleep(1)
            
            return {
                'success': True,
                'message': f'Sent alerts to {len(sent_channels)} channels',
                'details': {'channels': sent_channels, 'escalation_level': escalation_level}
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to send alert: {e}'}
    
    async def _run_script(self, parameters: Dict, alert: Dict) -> Dict:
        """Run a custom script"""
        try:
            script_path = parameters.get('script_path')
            script_args = parameters.get('args', [])
            
            if not script_path:
                return {'success': False, 'message': 'No script path provided'}
            
            # Execute script with timeout
            result = subprocess.run(
                [script_path] + script_args,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                'success': result.returncode == 0,
                'message': f'Script executed with return code {result.returncode}',
                'details': {
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'return_code': result.returncode
                }
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'message': 'Script execution timed out'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to run script: {e}'}
    
    def add_custom_action(self, action: SelfHealingAction):
        """Add a custom self-healing action"""
        self.self_healing_actions.append(action)
        logger.info(f"Added custom action: {action.name}")
    
    def get_action_history(self, hours: int = 24) -> List[Dict]:
        """Get action execution history"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            action for action in self.action_history
            if action['timestamp'] >= cutoff_time
        ]
    
    def get_active_alerts(self) -> Dict:
        """Get currently active alerts"""
        return self.active_alerts
    
    def resolve_alert(self, alert_id: str, resolution_note: str = ""):
        """Mark an alert as resolved"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert['resolved_at'] = datetime.now()
            alert['resolution_note'] = resolution_note
            self.resolved_alerts[alert_id] = alert
            logger.info(f"Resolved alert: {alert_id}")
    
    def get_self_healing_stats(self) -> Dict:
        """Get self-healing statistics"""
        total_actions = len(self.action_history)
        successful_actions = len([a for a in self.action_history if a['result'].get('success', False)])
        
        return {
            'total_actions_executed': total_actions,
            'successful_actions': successful_actions,
            'success_rate': (successful_actions / total_actions * 100) if total_actions > 0 else 0,
            'active_alerts': len(self.active_alerts),
            'resolved_alerts': len(self.resolved_alerts),
            'enabled_actions': len([a for a in self.self_healing_actions if a.enabled])
        }