"""Deployment coordination through configured deployment services."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DeploymentStrategy(str, Enum):
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    IMMEDIATE = "immediate"


class HealthCheckType(str, Enum):
    HTTP = "http"
    TCP = "tcp"
    GRPC = "grpc"
    CUSTOM = "custom"


@dataclass
class DeploymentConfig:
    service_name: str
    version: str
    strategy: DeploymentStrategy
    health_checks: List[Dict[str, Any]]
    rollback_triggers: List[Dict[str, Any]]
    monitoring_duration_minutes: int
    success_criteria: Dict[str, Any]
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not self.service_name or not self.version:
            raise ValueError("service_name and version are required")
        if self.monitoring_duration_minutes <= 0:
            raise ValueError("monitoring_duration_minutes must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        required = {
            "error_rate_threshold",
            "latency_p95_threshold_ms",
            "minimum_success_rate",
        }
        missing = required.difference(self.success_criteria)
        if missing:
            raise ValueError(f"success_criteria missing: {sorted(missing)}")


class AIOpsDeploymentOrchestrator:
    """Coordinate deployment lifecycle through an approved external service."""

    def __init__(
        self,
        executor_url: str | None = None,
        advisor: "MLDeploymentAdvisor | None" = None,
    ):
        self.executor_url = executor_url or os.getenv("AIOPS_DEPLOYMENT_EXECUTOR_URL")
        self.active_deployments: Dict[str, Dict[str, Any]] = {}
        self.deployment_history: List[Dict[str, Any]] = []
        self.ml_deployment_advisor = advisor or MLDeploymentAdvisor()

    async def deploy_with_intelligence(
        self, config: DeploymentConfig, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        deployment_id = f"{config.service_name}:{config.version}"
        risk_analysis = await self.ml_deployment_advisor.analyze_deployment_risk(
            config, context
        )
        if not risk_analysis.get("success", False):
            return {
                "deployment_id": deployment_id,
                "risk_analysis": risk_analysis,
                "deployment_result": risk_analysis,
            }
        deployment_result = await self._dispatch(
            "deploy", deployment_id, config, context
        )
        record = {
            "deployment_id": deployment_id,
            "config": config,
            "risk_analysis": risk_analysis,
            "result": deployment_result,
        }
        self.deployment_history.append(record)
        return {
            "deployment_id": deployment_id,
            "risk_analysis": risk_analysis,
            "strategy_used": config.strategy.value,
            "deployment_result": deployment_result,
            "recommendations": self._generate_deployment_recommendations(
                deployment_result
            ),
        }

    async def _dispatch(
        self,
        operation: str,
        deployment_id: str,
        config: DeploymentConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.executor_url:
            return {
                "success": False,
                "error": "integration_unavailable",
                "message": "Deployment executor is not configured",
            }
        payload = {
            "operation": operation,
            "deployment_id": deployment_id,
            "service_name": config.service_name,
            "version": config.version,
            "strategy": config.strategy.value,
            "health_checks": config.health_checks,
            "rollback_triggers": config.rollback_triggers,
            "monitoring_duration_minutes": config.monitoring_duration_minutes,
            "success_criteria": config.success_criteria,
            "context": context,
        }
        try:
            response = await asyncio.to_thread(
                requests.post,
                self.executor_url,
                json=payload,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {
                "success": False,
                "error": "integration_unavailable",
                "message": str(exc),
            }
        if not isinstance(body, dict) or not isinstance(body.get("success"), bool):
            return {
                "success": False,
                "error": "invalid_integration_response",
                "message": "Deployment executor returned an invalid response",
            }
        return body

    def _generate_deployment_recommendations(
        self, deployment_result: Dict[str, Any]
    ) -> List[str]:
        recommendations = deployment_result.get("recommendations", [])
        return (
            [item for item in recommendations if isinstance(item, str)]
            if isinstance(recommendations, list)
            else []
        )


class MLDeploymentAdvisor:
    """Risk analysis adapter; it never invents a local risk score."""

    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or os.getenv("AIOPS_DEPLOYMENT_ADVISOR_URL")

    async def analyze_deployment_risk(
        self, config: DeploymentConfig, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self.endpoint:
            return {
                "success": False,
                "error": "integration_unavailable",
                "message": "Deployment advisor is not configured",
            }
        payload = {
            "service_name": config.service_name,
            "version": config.version,
            "strategy": config.strategy.value,
            "context": context,
        }
        try:
            response = await asyncio.to_thread(
                requests.post,
                self.endpoint,
                json=payload,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {
                "success": False,
                "error": "integration_unavailable",
                "message": str(exc),
            }
        if not isinstance(body, dict) or not isinstance(body.get("success"), bool):
            return {
                "success": False,
                "error": "invalid_integration_response",
                "message": "Deployment advisor returned an invalid response",
            }
        return body
