"""Adapters for external operational systems.

The adapters fail explicitly when a source is not configured or returns an
invalid response. They never manufacture telemetry, incidents, or model output.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, cast

import requests

from .config import Settings
from .security import fingerprint


class IntegrationUnavailable(RuntimeError):
    """Raised when an external source cannot provide trustworthy data."""


class PrometheusAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def query(self, expression: str | None) -> list[dict[str, Any]]:
        if not self.settings.prometheus_url:
            raise IntegrationUnavailable("Prometheus is not configured")
        if not expression:
            raise IntegrationUnavailable(
                "The requested Prometheus query is not configured"
            )
        url = self.settings.prometheus_url.rstrip("/") + "/api/v1/query"
        try:
            response = self.session.get(
                url,
                params={"query": expression},
                timeout=self.settings.prometheus_timeout_seconds,
                verify=self.settings.verify_tls,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IntegrationUnavailable(f"Prometheus query failed: {exc}") from exc
        if payload.get("status") != "success":
            raise IntegrationUnavailable("Prometheus returned an unsuccessful response")
        result = payload.get("data", {}).get("result")
        if not isinstance(result, list):
            raise IntegrationUnavailable(
                "Prometheus response did not contain a result vector"
            )
        return [self._normalize(item) for item in result if isinstance(item, dict)]

    def _normalize(self, item: Mapping[str, Any]) -> dict[str, Any]:
        metric = item.get("metric")
        value = item.get("value")
        if (
            not isinstance(metric, Mapping)
            or not isinstance(value, list)
            or len(value) != 2
        ):
            raise IntegrationUnavailable("Prometheus returned a malformed sample")
        try:
            timestamp = float(value[0])
            numeric_value = float(value[1])
        except (TypeError, ValueError) as exc:
            raise IntegrationUnavailable(
                "Prometheus returned a non-numeric sample"
            ) from exc
        name = str(metric.get("__name__", "unknown"))
        labels = {
            str(key): str(val) for key, val in metric.items() if key != "__name__"
        }
        return {
            "name": name,
            "value": numeric_value,
            "timestamp": timestamp,
            "labels": labels,
        }


class AlertmanagerAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def active_alerts(self) -> list[dict[str, Any]]:
        if not self.settings.alertmanager_url:
            raise IntegrationUnavailable("Alertmanager is not configured")
        url = self.settings.alertmanager_url.rstrip("/") + "/api/v2/alerts"
        try:
            response = self.session.get(
                url,
                params={"active": "true", "silenced": "false", "inhibited": "false"},
                timeout=self.settings.prometheus_timeout_seconds,
                verify=self.settings.verify_tls,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IntegrationUnavailable(f"Alertmanager request failed: {exc}") from exc
        if not isinstance(payload, list):
            raise IntegrationUnavailable("Alertmanager response was not a list")
        return [self._normalize(item) for item in payload if isinstance(item, dict)]

    def create_silence(
        self,
        matchers: list[dict[str, Any]],
        duration_minutes: int,
        comment: str,
        created_by: str,
    ) -> dict[str, Any]:
        if not self.settings.alertmanager_url:
            raise IntegrationUnavailable("Alertmanager is not configured")
        now = datetime.now(timezone.utc)
        payload = {
            "matchers": matchers,
            "startsAt": now.isoformat(),
            "endsAt": (now + timedelta(minutes=duration_minutes)).isoformat(),
            "createdBy": created_by,
            "comment": comment,
        }
        url = self.settings.alertmanager_url.rstrip("/") + "/api/v2/silences"
        try:
            response = self.session.post(
                url,
                json=cast(Any, payload),
                timeout=self.settings.prometheus_timeout_seconds,
                verify=self.settings.verify_tls,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IntegrationUnavailable(
                f"Alertmanager silence request failed: {exc}"
            ) from exc
        if not isinstance(result, Mapping) or not result.get("silenceId"):
            raise IntegrationUnavailable(
                "Alertmanager did not return a silence identifier"
            )
        return {"silence_id": result["silenceId"], "ends_at": payload["endsAt"]}

    @staticmethod
    def _normalize(item: Mapping[str, Any]) -> dict[str, Any]:
        raw_labels = item.get("labels")
        labels: Mapping[str, Any] = (
            raw_labels if isinstance(raw_labels, Mapping) else {}
        )
        raw_annotations = item.get("annotations")
        annotations: Mapping[str, Any] = (
            raw_annotations if isinstance(raw_annotations, Mapping) else {}
        )
        starts_at = item.get("startsAt") or item.get("updatedAt")
        return {
            "id": str(item.get("fingerprint") or fingerprint(str(labels))),
            "name": str(labels.get("alertname") or "unclassified"),
            "severity": str(labels.get("severity") or "unknown"),
            "labels": {str(key): str(value) for key, value in labels.items()},
            "message": str(
                annotations.get("description") or annotations.get("summary") or ""
            ),
            "timestamp": starts_at,
            "source": "alertmanager",
            "status": (
                str(item.get("status", {}).get("state", "active"))
                if isinstance(item.get("status"), Mapping)
                else "active"
            ),
        }


class ModelAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def answer(self, query: str, context: Mapping[str, Any]) -> dict[str, Any]:
        if not self.settings.llm_url or not self.settings.llm_model:
            raise IntegrationUnavailable(
                "The external model endpoint and model identifier are not configured"
            )
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Answer only from the supplied operational context. State uncertainty when context is insufficient.",
                },
                {"role": "user", "content": query},
            ],
            "metadata": {"context": context},
        }
        try:
            response = self.session.post(
                self.settings.llm_url,
                json=cast(Any, payload),
                headers=headers,
                timeout=self.settings.prometheus_timeout_seconds,
                verify=self.settings.verify_tls,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise IntegrationUnavailable(f"Model request failed: {exc}") from exc
        answer = self._extract_answer(result)
        return {"response": answer, "model": self.settings.llm_model}

    @staticmethod
    def _extract_answer(payload: Mapping[str, Any]) -> str:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = (
                choices[0].get("message") if isinstance(choices[0], Mapping) else None
            )
            content = message.get("content") if isinstance(message, Mapping) else None
            if isinstance(content, str) and content.strip():
                return content.strip()
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        raise IntegrationUnavailable("Model response did not contain text output")
