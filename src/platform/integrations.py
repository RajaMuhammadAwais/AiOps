"""Adapters for external operational systems.

The adapters implement the response contracts documented in OPERATIONS.md.
They fail explicitly on unavailable or malformed upstream data and never
manufacture telemetry, incidents, or model output.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Mapping, cast

import requests

from .config import Settings


class IntegrationUnavailable(RuntimeError):
    """Raised when an external source cannot provide trustworthy data."""


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise IntegrationUnavailable(f"Prometheus {label} was not numeric")
    try:
        parsed = float(value)
    except (ValueError, OverflowError) as exc:
        raise IntegrationUnavailable(f"Prometheus {label} was not numeric") from exc
    if not math.isfinite(parsed):
        raise IntegrationUnavailable(f"Prometheus {label} was not finite")
    return parsed


def _required_datetime(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntegrationUnavailable(f"Alertmanager alert is missing {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntegrationUnavailable(
            f"Alertmanager alert has an invalid {label} timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IntegrationUnavailable(
            f"Alertmanager alert has an invalid {label} timestamp"
        )
    return value


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
        upstream = self.settings.upstream("prometheus")
        try:
            response = self.session.get(
                url,
                params={"query": expression},
                headers=upstream.headers,
                auth=upstream.basic_auth,
                timeout=upstream.timeout_seconds,
                verify=upstream.verify_tls,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, RecursionError) as exc:
            raise IntegrationUnavailable("Prometheus request failed") from exc
        if not isinstance(payload, Mapping) or payload.get("status") != "success":
            raise IntegrationUnavailable("Prometheus returned an unsuccessful response")
        data = payload.get("data")
        if not isinstance(data, Mapping) or data.get("resultType") != "vector":
            raise IntegrationUnavailable(
                "Prometheus response was not an instant vector"
            )
        result = data.get("result")
        if not isinstance(result, list) or any(
            not isinstance(item, Mapping) for item in result
        ):
            raise IntegrationUnavailable(
                "Prometheus response did not contain valid vector samples"
            )
        return [self._normalize(item) for item in result]

    @staticmethod
    def _normalize(item: Mapping[str, Any]) -> dict[str, Any]:
        metric = item.get("metric")
        value = item.get("value")
        if not isinstance(metric, Mapping) or any(
            not isinstance(key, str) or not isinstance(label, str)
            for key, label in metric.items()
        ):
            raise IntegrationUnavailable("Prometheus returned malformed labels")
        if not isinstance(value, list) or len(value) != 2:
            raise IntegrationUnavailable("Prometheus returned a malformed sample")
        if isinstance(value[0], bool) or not isinstance(value[0], (int, float)):
            raise IntegrationUnavailable("Prometheus timestamp was not numeric")
        if not isinstance(value[1], str):
            raise IntegrationUnavailable("Prometheus sample was not a string")
        timestamp = _finite_number(value[0], "timestamp")
        numeric_value = _finite_number(value[1], "sample")
        name = metric.get("__name__", "")
        if not isinstance(name, str):
            raise IntegrationUnavailable("Prometheus returned a malformed metric name")
        labels = {key: val for key, val in metric.items() if key != "__name__"}
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
        upstream = self.settings.upstream("alertmanager")
        try:
            response = self.session.get(
                url,
                params={"active": "true", "silenced": "false", "inhibited": "false"},
                headers=upstream.headers,
                auth=upstream.basic_auth,
                timeout=upstream.timeout_seconds,
                verify=upstream.verify_tls,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, RecursionError) as exc:
            raise IntegrationUnavailable("Alertmanager request failed") from exc
        if not isinstance(payload, list) or any(
            not isinstance(item, Mapping) for item in payload
        ):
            raise IntegrationUnavailable(
                "Alertmanager response was not a valid alert list"
            )
        return [self._normalize(item) for item in payload]

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
        upstream = self.settings.upstream("alertmanager")
        try:
            response = self.session.post(
                url,
                json=cast(Any, payload),
                headers=upstream.headers,
                auth=upstream.basic_auth,
                timeout=upstream.timeout_seconds,
                verify=upstream.verify_tls,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError, RecursionError) as exc:
            raise IntegrationUnavailable("Alertmanager silence request failed") from exc
        if (
            not isinstance(result, Mapping)
            or not isinstance(result.get("silenceID"), str)
            or not result.get("silenceID", "").strip()
        ):
            raise IntegrationUnavailable(
                "Alertmanager did not return a valid silence identifier"
            )
        return {"silence_id": result["silenceID"], "ends_at": payload["endsAt"]}

    @staticmethod
    def _normalize(item: Mapping[str, Any]) -> dict[str, Any]:
        fingerprint = item.get("fingerprint")
        labels = item.get("labels")
        annotations = item.get("annotations")
        receivers = item.get("receivers")
        status = item.get("status")
        starts_at = _required_datetime(item.get("startsAt"), "startsAt")
        _required_datetime(item.get("updatedAt"), "updatedAt")
        _required_datetime(item.get("endsAt"), "endsAt")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise IntegrationUnavailable(
                "Alertmanager alert is missing its fingerprint"
            )
        if not isinstance(labels, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise IntegrationUnavailable("Alertmanager alert has malformed labels")
        if not isinstance(annotations, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in annotations.items()
        ):
            raise IntegrationUnavailable("Alertmanager alert has malformed annotations")
        if not isinstance(receivers, list) or any(
            not isinstance(receiver, Mapping)
            or not isinstance(receiver.get("name"), str)
            for receiver in receivers
        ):
            raise IntegrationUnavailable("Alertmanager alert has malformed receivers")
        if (
            not isinstance(status, Mapping)
            or not isinstance(status.get("state"), str)
            or status.get("state") not in {"unprocessed", "active", "suppressed"}
            or any(
                not isinstance(status.get(key), list)
                or any(not isinstance(value, str) for value in status.get(key, []))
                for key in ("silencedBy", "inhibitedBy", "mutedBy")
            )
        ):
            raise IntegrationUnavailable("Alertmanager alert has malformed status")
        name = labels.get("alertname")
        if not isinstance(name, str) or not name.strip():
            raise IntegrationUnavailable("Alertmanager alert is missing alertname")
        return {
            "id": fingerprint,
            "name": name,
            "severity": labels.get("severity", ""),
            "labels": dict(labels),
            "message": annotations.get("description") or annotations.get("summary", ""),
            "timestamp": starts_at,
            "source": "alertmanager",
            "status": status["state"],
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
        upstream = self.settings.upstream("llm")
        headers = {"Content-Type": "application/json", **upstream.headers}
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Answer only from the supplied operational context. "
                        "State uncertainty when context is insufficient."
                    ),
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
                auth=upstream.basic_auth,
                timeout=upstream.timeout_seconds,
                verify=upstream.verify_tls,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError, RecursionError) as exc:
            raise IntegrationUnavailable("Model request failed") from exc
        if not isinstance(result, Mapping):
            raise IntegrationUnavailable("Model response was not an object")
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
