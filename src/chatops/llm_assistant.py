"""
LLM-powered assistant for incident analysis and ChatOps
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import os
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMAssistant:
    """AI assistant for incident management and analysis"""
    
    def __init__(self):
        self.client = None
        self.model = "gpt-4o"  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.client = OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully")
            else:
                logger.warning("OPENAI_API_KEY not found in environment variables")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    
    async def explain_incident(self, alert: Dict, anomalies: List[Dict]) -> Dict:
        """Generate AI explanation for an incident"""
        if not self.client:
            return {
                'description': 'Alert detected but AI analysis unavailable',
                'explanation': 'OpenAI client not initialized',
                'root_cause': 'Unknown - AI analysis unavailable',
                'predicted_time': None
            }
        
        try:
            # Prepare context for the LLM
            context = self._prepare_incident_context(alert, anomalies)
            
            prompt = f"""
            You are an expert Site Reliability Engineer analyzing a system incident. 
            
            Alert Details:
            - Name: {alert.get('name', 'Unknown')}
            - Severity: {alert.get('severity', 'unknown')}
            - Message: {alert.get('message', 'No message')}
            - Labels: {json.dumps(alert.get('labels', {}), indent=2)}
            
            Detected Anomalies:
            {json.dumps(anomalies, indent=2, default=str)}
            
            Please provide a comprehensive incident analysis in JSON format with the following structure:
            {{
                "description": "Brief human-readable description of the incident",
                "explanation": "Detailed technical explanation of what's happening",
                "root_cause": "Most likely root cause analysis",
                "predicted_time": "Estimated resolution time in minutes (integer)",
                "impact_assessment": "Assessment of system impact",
                "recommended_actions": ["action1", "action2", "action3"],
                "monitoring_points": ["metric1", "metric2", "metric3"]
            }}
            
            Focus on actionable insights and be specific about technical details.
            """
            
            response = await self._make_openai_request(prompt)
            
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    'description': f'Incident: {alert.get("name", "Unknown")}',
                    'explanation': response,
                    'root_cause': 'Analysis provided in explanation',
                    'predicted_time': 30
                }
                
        except Exception as e:
            logger.error(f"Error generating incident explanation: {e}")
            return {
                'description': f'Alert: {alert.get("name", "Unknown")}',
                'explanation': f'Error generating AI analysis: {e}',
                'root_cause': 'Unable to determine - analysis failed',
                'predicted_time': None
            }
    
    async def chat_query(self, query: str, context: Dict) -> str:
        """Process chat query about system status or incidents"""
        if not self.client:
            return "AI assistant unavailable - OpenAI client not initialized. Please provide OPENAI_API_KEY."
        
        try:
            # Prepare system context
            system_context = self._prepare_chat_context(context)
            
            prompt = f"""
            You are an AIOps assistant helping with system monitoring and incident management.
            
            Current System Context:
            {system_context}
            
            User Query: {query}
            
            Please provide a helpful, concise response based on the current system state and historical data.
            Focus on actionable information and be specific about any issues or recommendations.
            """
            
            response = await self._make_openai_request(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat query: {e}")
            return f"Error processing your query: {e}"
    
    async def analyze_alert_pattern(self, alerts: List[Dict]) -> Dict:
        """Analyze patterns in alerts to identify trends"""
        if not self.client or not alerts:
            return {'pattern_analysis': 'No alerts to analyze or AI unavailable'}
        
        try:
            # Summarize alerts for analysis
            alert_summary = []
            for alert in alerts[-20:]:  # Last 20 alerts
                alert_summary.append({
                    'name': alert.get('name', 'unknown'),
                    'severity': alert.get('severity', 'unknown'),
                    'timestamp': str(alert.get('timestamp', '')),
                    'message': alert.get('message', '')[:100]  # Truncate long messages
                })
            
            prompt = f"""
            Analyze the following alert patterns to identify trends, recurring issues, and potential root causes.
            
            Recent Alerts:
            {json.dumps(alert_summary, indent=2)}
            
            Please provide analysis in JSON format:
            {{
                "pattern_analysis": "Description of identified patterns",
                "recurring_issues": ["issue1", "issue2"],
                "trend_analysis": "Analysis of trends over time",
                "recommendations": ["recommendation1", "recommendation2"],
                "priority_areas": ["area1", "area2"]
            }}
            """
            
            response = await self._make_openai_request(prompt)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {'pattern_analysis': response}
                
        except Exception as e:
            logger.error(f"Error analyzing alert patterns: {e}")
            return {'pattern_analysis': f'Error in pattern analysis: {e}'}
    
    async def generate_runbook(self, incident_type: str, historical_incidents: List[Dict]) -> Dict:
        """Generate runbook for common incident types"""
        if not self.client:
            return {'runbook': 'AI unavailable for runbook generation'}
        
        try:
            prompt = f"""
            Generate a comprehensive runbook for handling incidents of type: {incident_type}
            
            Based on historical incidents:
            {json.dumps(historical_incidents, indent=2, default=str)}
            
            Please provide a runbook in JSON format:
            {{
                "incident_type": "{incident_type}",
                "diagnosis_steps": ["step1", "step2", "step3"],
                "resolution_steps": ["step1", "step2", "step3"],
                "verification_steps": ["step1", "step2"],
                "escalation_criteria": "When to escalate",
                "common_causes": ["cause1", "cause2"],
                "prevention_measures": ["measure1", "measure2"],
                "estimated_resolution_time": "time estimate"
            }}
            """
            
            response = await self._make_openai_request(prompt)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {'runbook': response}
                
        except Exception as e:
            logger.error(f"Error generating runbook: {e}")
            return {'runbook': f'Error generating runbook: {e}'}
    
    async def create_alert_rule(self, natural_language_rule: str) -> Dict:
        """Convert natural language to alert rule configuration"""
        if not self.client:
            return {'error': 'AI unavailable for rule creation'}
        
        try:
            prompt = f"""
            Convert the following natural language alert rule into a structured configuration:
            
            Rule: "{natural_language_rule}"
            
            Please provide the alert rule configuration in JSON format:
            {{
                "rule_name": "descriptive_name",
                "condition": "prometheus_query_or_condition",
                "threshold": "numeric_threshold",
                "duration": "time_duration",
                "severity": "critical/high/medium/low",
                "description": "human_readable_description",
                "labels": {{"key": "value"}},
                "annotations": {{"summary": "alert_summary", "description": "detailed_description"}}
            }}
            
            Focus on creating valid Prometheus-style alert rules where possible.
            """
            
            response = await self._make_openai_request(prompt)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {'rule_config': response}
                
        except Exception as e:
            logger.error(f"Error creating alert rule: {e}")
            return {'error': f'Error creating alert rule: {e}'}
    
    def _prepare_incident_context(self, alert: Dict, anomalies: List[Dict]) -> str:
        """Prepare context for incident analysis"""
        context_parts = [
            f"Alert Severity: {alert.get('severity', 'unknown')}",
            f"Alert Source: {alert.get('source', 'unknown')}",
            f"Number of Anomalies: {len(anomalies)}"
        ]
        
        # Add anomaly types
        anomaly_types = set()
        for anomaly in anomalies:
            anomaly_types.add(anomaly.get('type', 'unknown'))
        
        context_parts.append(f"Anomaly Types: {', '.join(anomaly_types)}")
        
        return "; ".join(context_parts)
    
    def _prepare_chat_context(self, context: Dict) -> str:
        """Prepare context for chat queries"""
        context_parts = []
        
        # System status
        system_status = context.get('system_status', {})
        if system_status:
            context_parts.append(f"System Health: {system_status.get('status', 'unknown')}")
            context_parts.append(f"CPU Usage: {system_status.get('cpu_usage', 0):.1f}%")
            context_parts.append(f"Memory Usage: {system_status.get('memory_usage', 0):.1f}%")
        
        # Recent incidents
        incidents = context.get('incidents', [])
        if incidents:
            context_parts.append(f"Recent Incidents: {len(incidents)}")
            open_incidents = [i for i in incidents if i.status.value == 'open']
            if open_incidents:
                context_parts.append(f"Open Incidents: {len(open_incidents)}")
        
        # Recent alerts
        alerts = context.get('alerts', [])
        if alerts:
            context_parts.append(f"Recent Alerts: {len(alerts)}")
        
        return "\n".join(context_parts) if context_parts else "No context available"
    
    async def _make_openai_request(self, prompt: str) -> str:
        """Make request to OpenAI API"""
        try:
            if not self.client:
                return "AI assistant unavailable - please provide OPENAI_API_KEY"
                
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert Site Reliability Engineer and AIOps specialist."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            return content if content else "No response from AI"
            
        except Exception as e:
            logger.error(f"OpenAI API request failed: {e}")
            return f"AI request failed: {e}"
    
    def is_available(self) -> bool:
        """Check if LLM assistant is available"""
        return self.client is not None