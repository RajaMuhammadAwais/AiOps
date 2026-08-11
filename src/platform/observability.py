"""Dependency-light observability and reliability primitives."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
import threading
import time
from typing import Any, Deque, Dict, Iterable
from uuid import uuid4


class JsonFormatter(logging.Formatter):
    """Emit structured logs that can be shipped to a centralized log system."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def new_request_id() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class RequestSample:
    method: str
    path: str
    status: int
    duration_seconds: float
    timestamp: float


class MetricsRegistry:
    """Small process-local metrics registry with bounded latency samples."""

    def __init__(self, max_samples: int = 2000) -> None:
        self._counts: Dict[tuple[str, str, int], int] = defaultdict(int)
        self._durations: Deque[RequestSample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def observe(
        self, method: str, path: str, status: int, duration_seconds: float
    ) -> None:
        with self._lock:
            self._counts[(method, path, status)] += 1
            self._durations.append(
                RequestSample(
                    method, path, status, max(0.0, duration_seconds), time.time()
                )
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
            durations = list(self._durations)
        total = sum(counts.values())
        errors = sum(
            value for (method, path, status), value in counts.items() if status >= 500
        )
        latencies = sorted(sample.duration_seconds for sample in durations)
        return {
            "total_requests": total,
            "error_requests": errors,
            "latency_samples": len(latencies),
            "p50_latency_ms": _percentile(latencies, 0.50) * 1000 if latencies else 0.0,
            "p95_latency_ms": _percentile(latencies, 0.95) * 1000 if latencies else 0.0,
            "p99_latency_ms": _percentile(latencies, 0.99) * 1000 if latencies else 0.0,
        }

    def slo_snapshot(self, target: float, window_minutes: int) -> dict[str, Any]:
        now = time.time()
        cutoff = now - (window_minutes * 60)
        with self._lock:
            samples = [
                sample for sample in self._durations if sample.timestamp >= cutoff
            ]
        total = len(samples)
        errors = sum(1 for sample in samples if sample.status >= 500)
        good = total - errors
        availability = (good / total * 100.0) if total else 100.0
        budget = max(0.0, availability - target)
        consumed = max(0.0, target - availability)
        burn_rate = (
            (100.0 - availability) / max(100.0 - target, 0.0001) if total else 0.0
        )
        return {
            "window_minutes": window_minutes,
            "target_percent": target,
            "availability_percent": round(availability, 4),
            "total_requests": total,
            "error_requests": errors,
            "error_budget_remaining_percent": round(budget, 4),
            "error_budget_consumed_percent": round(consumed, 4),
            "burn_rate": round(burn_rate, 4),
            "within_objective": availability >= target,
        }

    def prometheus(self, service_name: str) -> str:
        with self._lock:
            counts = dict(self._counts)
            samples = list(self._durations)
        lines = [
            "# HELP aiops_http_requests_total Total HTTP requests handled by the service.",
            "# TYPE aiops_http_requests_total counter",
        ]
        for (method, path, status), count in sorted(counts.items()):
            labels = _labels(
                service=service_name, method=method, path=path, status=str(status)
            )
            lines.append(f"aiops_http_requests_total{{{labels}}} {count}")
        total_duration = sum(sample.duration_seconds for sample in samples)
        lines.extend(
            [
                "# HELP aiops_http_request_duration_seconds_sum Cumulative observed HTTP duration.",
                "# TYPE aiops_http_request_duration_seconds_sum counter",
                f'aiops_http_request_duration_seconds_sum{{service="{_escape(service_name)}"}} {total_duration:.6f}',
                "# HELP aiops_http_latency_samples Number of bounded latency samples retained.",
                "# TYPE aiops_http_latency_samples gauge",
                f'aiops_http_latency_samples{{service="{_escape(service_name)}"}} {len(samples)}',
            ]
        )
        return "\n".join(lines) + "\n"


def _percentile(values: Iterable[float], fraction: float) -> float:
    ordered = list(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**values: str) -> str:
    return ",".join(f'{key}="{_escape(value)}"' for key, value in values.items())
