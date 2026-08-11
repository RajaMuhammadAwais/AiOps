"""Alert lifecycle management with an explicit external action boundary."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

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
    id: str
    name: str
    action_type: ActionType
    condition: str
    parameters: Dict[str, Any]
    cooldown_minutes: int = 15
    max_retries: int = 3
    enabled: bool = True


class AlertManager:
    """Manage alerts and delegate actions to an approved external executor.

    The manager deliberately has no built-in actions. Deployments must load
    action policy from a controlled configuration or policy service and provide
    an executor URL before any action can be dispatched.
    """

    def __init__(
        self,
        executor_url: str | None = None,
        actions: Optional[List[SelfHealingAction]] = None,
    ):
        self.executor_url = executor_url or os.getenv("AIOPS_ACTION_EXECUTOR_URL")
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        self.resolved_alerts: Dict[str, Dict[str, Any]] = {}
        self.self_healing_actions: List[SelfHealingAction] = list(actions or [])
        self.action_history: List[Dict[str, Any]] = []
        self.cooldown_tracker: Dict[str, datetime] = {}

    async def process_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        alert_id = alert.get("id")
        if not isinstance(alert_id, str) or not alert_id:
            return {"processed": False, "message": "Alert id is required"}
        self.active_alerts[alert_id] = {
            **alert,
            "received_at": datetime.now(),
            "processed": False,
        }
        actions_taken = []
        for action in self.self_healing_actions:
            if action.enabled and self._should_trigger_action(action, alert):
                result = await self._execute_action(action, alert)
                actions_taken.append(
                    {
                        "action": action.name,
                        "result": result,
                        "timestamp": datetime.now(),
                    }
                )
        self.active_alerts[alert_id]["processed"] = True
        self.active_alerts[alert_id]["actions_taken"] = actions_taken
        return {
            "alert_id": alert_id,
            "processed": True,
            "actions_taken": len(actions_taken),
            "actions": actions_taken,
        }

    def _should_trigger_action(
        self, action: SelfHealingAction, alert: Dict[str, Any]
    ) -> bool:
        if self._is_in_cooldown(action.id):
            return False
        condition = action.condition
        severity = alert.get("severity")
        values = {
            "cpu_usage": self._extract_metric_value(alert, "cpu_usage"),
            "memory_usage": self._extract_metric_value(alert, "memory_usage"),
            "load_average": self._extract_metric_value(alert, "load_average"),
            "response_time": self._extract_metric_value(alert, "response_time"),
        }
        if "severity == 'critical'" in condition and severity == "critical":
            return True
        for metric, value in values.items():
            marker = f"{metric} > "
            if marker in condition and value is not None:
                try:
                    threshold = float(condition.split(marker, 1)[1].split()[0])
                except (TypeError, ValueError, IndexError):
                    continue
                if value > threshold:
                    return True
        return False

    @staticmethod
    def _extract_metric_value(
        alert: Dict[str, Any], metric_name: str
    ) -> Optional[float]:
        try:
            for metric in alert.get("metrics", []):
                if metric_name in str(metric.get("name", "")).lower():
                    return float(metric.get("value"))
            labels = alert.get("labels", {})
            if metric_name in labels:
                return float(labels[metric_name])
        except (TypeError, ValueError):
            return None
        return None

    def _is_in_cooldown(self, action_id: str) -> bool:
        last_execution = self.cooldown_tracker.get(action_id)
        action = next(
            (item for item in self.self_healing_actions if item.id == action_id), None
        )
        return bool(
            last_execution
            and action
            and datetime.now() - last_execution
            < timedelta(minutes=action.cooldown_minutes)
        )

    async def _execute_action(
        self, action: SelfHealingAction, alert: Dict[str, Any]
    ) -> Dict[str, Any]:
        result: Dict[str, Any]
        if not self.executor_url:
            result = {
                "success": False,
                "message": "Action executor is not configured",
                "action_type": action.action_type.value,
            }
        else:
            result = await asyncio.to_thread(self._dispatch, action, alert)
        self.action_history.append(
            {
                "action_id": action.id,
                "action_name": action.name,
                "alert_id": alert.get("id"),
                "timestamp": datetime.now(),
                "result": result,
            }
        )
        if result.get("success"):
            self.cooldown_tracker[action.id] = datetime.now()
        return result

    def _dispatch(
        self, action: SelfHealingAction, alert: Dict[str, Any]
    ) -> Dict[str, Any]:
        timeout = action.parameters.get("timeout_seconds")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            return {
                "success": False,
                "message": "Action timeout_seconds must be supplied by action policy",
            }
        payload = {
            "action_type": action.action_type.value,
            "action_id": action.id,
            "parameters": action.parameters,
            "alert": {
                "id": alert.get("id"),
                "severity": alert.get("severity"),
                "labels": alert.get("labels", {}),
            },
        }
        try:
            response = requests.post(
                self.executor_url, json=payload, timeout=float(timeout)
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {
                "success": False,
                "message": f"Action executor request failed: {exc}",
            }
        if not isinstance(body, dict) or not isinstance(body.get("success"), bool):
            return {
                "success": False,
                "message": "Action executor returned an invalid response",
            }
        return body

    def add_custom_action(self, action: SelfHealingAction) -> None:
        self.self_healing_actions.append(action)

    def get_action_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            action
            for action in self.action_history
            if action["timestamp"] >= cutoff_time
        ]

    def get_active_alerts(self) -> Dict[str, Dict[str, Any]]:
        return self.active_alerts

    def resolve_alert(self, alert_id: str, resolution_note: str = "") -> None:
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert["resolved_at"] = datetime.now()
            alert["resolution_note"] = resolution_note
            self.resolved_alerts[alert_id] = alert

    def get_self_healing_stats(self) -> Dict[str, Any]:
        total_actions = len(self.action_history)
        successful_actions = sum(
            1
            for action in self.action_history
            if action["result"].get("success", False)
        )
        return {
            "total_actions_executed": total_actions,
            "successful_actions": successful_actions,
            "success_rate": (
                (successful_actions / total_actions * 100) if total_actions else 0
            ),
            "active_alerts": len(self.active_alerts),
            "resolved_alerts": len(self.resolved_alerts),
            "enabled_actions": sum(
                1 for action in self.self_healing_actions if action.enabled
            ),
        }
