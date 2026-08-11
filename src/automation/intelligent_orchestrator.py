"""
Intelligent Orchestrator for AIOps - Advanced workflow automation and decision making
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import logging
import os
import requests
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ActionPriority(Enum):
    IMMEDIATE = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AutomationRule:
    """Definition of an automation rule"""

    id: str
    name: str
    trigger_conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    priority: ActionPriority
    cooldown_minutes: int = 15
    enabled: bool = True
    approval_required: bool = False


class IntelligentOrchestrator:
    """Advanced automation orchestrator with ML-driven decision making"""

    def __init__(
        self,
        executor_url: str | None = None,
        rules: Optional[List[AutomationRule]] = None,
    ):
        self.executor_url = executor_url or os.getenv("AIOPS_ACTION_EXECUTOR_URL")
        self.automation_rules = {rule.id: rule for rule in (rules or [])}
        self.execution_history = []
        self.rate_limiters = {}

    async def orchestrate_response(self, incident_context: Dict[str, Any]) -> Dict:
        """Orchestrate intelligent response to incidents"""

        # Analyze incident complexity and determine response strategy
        response_strategy = self._determine_response_strategy(incident_context)

        # Execute coordinated response
        orchestration_result = await self._execute_coordinated_response(
            response_strategy, incident_context
        )

        return {
            "strategy": response_strategy,
            "orchestration_result": orchestration_result,
            "automation_effectiveness": self._calculate_effectiveness(
                orchestration_result
            ),
            "learning_insights": self._extract_learning_insights(orchestration_result),
        }

    def _determine_response_strategy(self, context: Dict) -> Dict:
        """Determine optimal response strategy using AI"""

        severity = context.get("severity", "medium")
        affected_services = context.get("affected_services", [])
        business_impact = context.get("business_impact", "low")

        if severity == "critical" or len(affected_services) > 5:
            return {
                "type": "emergency_response",
                "coordination_level": "full",
                "automation_level": "aggressive",
                "human_involvement": "immediate",
            }
        elif severity == "high" or business_impact == "high":
            return {
                "type": "standard_response",
                "coordination_level": "standard",
                "automation_level": "moderate",
                "human_involvement": "scheduled",
            }
        else:
            return {
                "type": "automated_response",
                "coordination_level": "minimal",
                "automation_level": "conservative",
                "human_involvement": "notification_only",
            }

    async def _execute_coordinated_response(
        self, strategy: Dict, context: Dict
    ) -> Dict:
        """Execute coordinated response based on strategy"""

        results = {
            "actions_taken": [],
            "success_rate": 0,
            "response_time_seconds": 0,
            "automation_efficiency": 0,
        }

        start_time = datetime.now()
        successful_actions = 0
        total_actions = 0

        coordination_level = strategy.get("coordination_level", "standard")

        if coordination_level == "full":
            # Execute comprehensive response
            actions = [
                {"type": "immediate_assessment", "priority": "critical"},
                {"type": "resource_isolation", "priority": "high"},
                {"type": "failover_execution", "priority": "high"},
                {"type": "stakeholder_notification", "priority": "medium"},
                {"type": "recovery_validation", "priority": "medium"},
            ]
        elif coordination_level == "standard":
            actions = [
                {"type": "diagnostic_collection", "priority": "high"},
                {"type": "targeted_remediation", "priority": "high"},
                {"type": "impact_mitigation", "priority": "medium"},
            ]
        else:
            actions = [
                {"type": "automated_remediation", "priority": "medium"},
                {"type": "monitoring_enhancement", "priority": "low"},
            ]

        for action in actions:
            try:
                action_result = await self._execute_orchestrated_action(action, context)
                results["actions_taken"].append(
                    {
                        "action": action["type"],
                        "result": action_result,
                        "timestamp": datetime.now(),
                    }
                )

                if action_result.get("success", False):
                    successful_actions += 1
                total_actions += 1

            except Exception as e:
                logger.error(f"Orchestrated action failed: {e}")
                total_actions += 1

        end_time = datetime.now()
        results["response_time_seconds"] = (end_time - start_time).total_seconds()
        results["success_rate"] = (
            successful_actions / total_actions if total_actions > 0 else 0
        )
        results["automation_efficiency"] = self._calculate_automation_efficiency(
            results
        )

        return results

    async def _execute_orchestrated_action(self, action: Dict, context: Dict) -> Dict:
        """Execute individual orchestrated action"""

        action_type = action["type"]

        if not self.executor_url:
            return {
                "success": False,
                "message": "Action executor is not configured",
                "action_type": action_type,
            }
        timeout = action.get("parameters", {}).get("timeout_seconds")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            return {
                "success": False,
                "message": "Action timeout_seconds must be supplied by policy",
            }
        payload = {"action": action, "context": context}
        try:
            response = await asyncio.to_thread(
                requests.post,
                self.executor_url,
                json=payload,
                timeout=float(timeout),
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {
                "success": False,
                "message": f"Action executor request failed: {exc}",
            }
        if not isinstance(result, dict) or not isinstance(result.get("success"), bool):
            return {
                "success": False,
                "message": "Action executor returned an invalid response",
            }
        return result

    def _calculate_automation_efficiency(self, results: Dict) -> float:
        """Calculate automation efficiency score"""
        success_rate = results.get("success_rate", 0)
        response_time = results.get("response_time_seconds", 300)

        # Efficiency decreases with longer response times
        time_efficiency = max(0, 1 - (response_time / 300))  # 5 minutes baseline

        return (success_rate * 0.7) + (time_efficiency * 0.3)

    def _calculate_effectiveness(self, orchestration_result: Dict) -> Dict:
        """Calculate overall orchestration effectiveness"""
        return {
            "response_speed": (
                "fast"
                if orchestration_result["response_time_seconds"] < 60
                else "standard"
            ),
            "action_success_rate": orchestration_result["success_rate"],
            "automation_efficiency": orchestration_result["automation_efficiency"],
            "overall_score": (
                orchestration_result["success_rate"] * 0.4
                + orchestration_result["automation_efficiency"] * 0.6
            ),
        }

    def _extract_learning_insights(self, orchestration_result: Dict) -> List[str]:
        """Extract insights for continuous learning"""
        insights = []

        success_rate = orchestration_result["success_rate"]
        efficiency = orchestration_result["automation_efficiency"]

        if success_rate < 0.8:
            insights.append(
                "Consider improving action reliability through better error handling"
            )

        if efficiency < 0.7:
            insights.append("Optimize response times through parallel execution")

        if orchestration_result["response_time_seconds"] > 120:
            insights.append("Investigate opportunities for faster decision making")

        insights.append("Continue monitoring orchestration patterns for optimization")

        return insights
