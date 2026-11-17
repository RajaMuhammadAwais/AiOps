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
    route: str
    scope: str
    status: int
    duration_seconds: float
    timestamp: float


class MetricsRegistry:
    """Local counters and rolling samples; Prometheus exports merge workers."""

    LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    HTTP_METHODS = frozenset(
        {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
    )
    SLI_DESCRIPTION = {
        "name": "api_request_availability",
        "good_event": "An API request receives a final 2xx or 3xx response.",
        "total_event": (
            "API requests receiving 2xx/3xx, 429, or 5xx responses in the window."
        ),
        "status_policy": {
            "2xx_3xx": "good numerator and denominator",
            "429": "bad event in denominator; request was not served",
            "4xx_except_429": "excluded from numerator and denominator as caller errors",
            "5xx": "bad event in denominator, including mapped dependency failures",
        },
    }

    def __init__(self, max_samples: int = 2000) -> None:
        # Keys contain only bounded method, route-template, scope, and status values.
        self._counts: Dict[tuple[str, str, str, int], int] = defaultdict(int)
        self._durations: Deque[RequestSample] = deque(maxlen=max_samples)
        self._histogram_counts: Dict[tuple[str, str, str], list[int]] = {}
        self._histogram_sums: Dict[tuple[str, str, str], float] = defaultdict(float)
        self._lock = threading.Lock()

    def observe(
        self,
        method: str,
        route: str,
        status: int,
        duration_seconds: float,
        *,
        include_in_sli: bool = True,
    ) -> None:
        normalized_method = method.upper()
        if normalized_method not in self.HTTP_METHODS:
            normalized_method = "OTHER"
        normalized_route = (
            route if route.startswith("/") and len(route) <= 200 else "__unmatched__"
        )
        scope = "api" if include_in_sli else "other"
        duration = max(0.0, duration_seconds)
        if not math.isfinite(duration):
            duration = 0.0
        bucket_key = (scope, normalized_method, normalized_route)
        with self._lock:
            self._counts[(scope, normalized_method, normalized_route, status)] += 1
            self._durations.append(
                RequestSample(
                    normalized_method,
                    normalized_route,
                    scope,
                    status,
                    duration,
                    time.time(),
                )
            )
            counts = self._histogram_counts.setdefault(
                bucket_key, [0] * (len(self.LATENCY_BUCKETS) + 1)
            )
            for index, upper_bound in enumerate(self.LATENCY_BUCKETS):
                if duration <= upper_bound:
                    counts[index] += 1
            counts[-1] += 1  # Prometheus +Inf bucket is the total observation count.
            self._histogram_sums[bucket_key] += duration

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = dict(self._counts)
            durations = list(self._durations)
        total = sum(counts.values())
        errors = sum(
            value
            for (_scope, _method, _route, status), value in counts.items()
            if status == 429 or 500 <= status < 600
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
        """Return an explicitly single-process rolling-window diagnostic snapshot."""
        cutoff = time.time() - (window_minutes * 60)
        with self._lock:
            samples = [
                sample
                for sample in self._durations
                if sample.scope == "api" and sample.timestamp >= cutoff
            ]
        good, total, excluded = _classify_sli_samples(samples)
        return _slo_result(
            good,
            total,
            target,
            window_minutes,
            source="process_local",
            aggregation_scope="single process; bounded in-memory sample window",
            excluded_client_errors=excluded,
        )

    @staticmethod
    def shared_slo_snapshot(
        good_events: float,
        total_events: float,
        target: float,
        window_minutes: int,
    ) -> dict[str, Any]:
        """Calculate the SLI from values aggregated by a shared Prometheus server."""
        if (
            not math.isfinite(good_events)
            or not math.isfinite(total_events)
            or good_events < 0
            or total_events < 0
            or good_events > total_events
        ):
            raise ValueError("Prometheus returned invalid SLI event counts")
        return _slo_result(
            good_events,
            total_events,
            target,
            window_minutes,
            source="prometheus",
            aggregation_scope="all instances scraped by configured Prometheus",
            excluded_client_errors=None,
        )

    def prometheus(self, service_name: str) -> str:
        """Export counters and a fixed-bucket histogram for cross-worker aggregation."""
        with self._lock:
            counts = dict(self._counts)
            histogram_counts = {
                key: list(value) for key, value in self._histogram_counts.items()
            }
            histogram_sums = dict(self._histogram_sums)
        lines = [
            "# HELP aiops_http_requests_total Total HTTP requests by bounded route and status.",
            "# TYPE aiops_http_requests_total counter",
        ]
        for (scope, method, route, status), count in sorted(counts.items()):
            labels = _labels(
                service=service_name,
                scope=scope,
                method=method,
                route=route,
                status=str(status),
            )
            lines.append(f"aiops_http_requests_total{{{labels}}} {count}")

        lines.extend(
            [
                "# HELP aiops_http_request_duration_seconds Request duration in seconds.",
                "# TYPE aiops_http_request_duration_seconds histogram",
            ]
        )
        bucket_bounds: tuple[float | None, ...] = (*self.LATENCY_BUCKETS, None)
        for (scope, method, route), bucket_counts in sorted(histogram_counts.items()):
            for bound, count in zip(bucket_bounds, bucket_counts):
                label_values = {
                    "service": service_name,
                    "scope": scope,
                    "method": method,
                    "route": route,
                    "le": "+Inf" if bound is None else _format_number(bound),
                }
                lines.append(
                    "aiops_http_request_duration_seconds_bucket"
                    f"{{{_labels(**label_values)}}} {count}"
                )
            labels = _labels(
                service=service_name, scope=scope, method=method, route=route
            )
            lines.append(
                f"aiops_http_request_duration_seconds_sum{{{labels}}} "
                f"{histogram_sums[(scope, method, route)]:.9f}"
            )
            lines.append(
                f"aiops_http_request_duration_seconds_count{{{labels}}} {bucket_counts[-1]}"
            )
        return "\n".join(lines) + "\n"


def _classify_sli_samples(samples: Iterable[RequestSample]) -> tuple[int, int, int]:
    good = 0
    total = 0
    excluded = 0
    for sample in samples:
        status = sample.status
        if 200 <= status < 400:
            good += 1
            total += 1
        elif status == 429 or 500 <= status < 600:
            total += 1
        elif 400 <= status < 500:
            excluded += 1
    return good, total, excluded


def _slo_result(
    good_events: float,
    total_events: float,
    target: float,
    window_minutes: int,
    *,
    source: str,
    aggregation_scope: str,
    excluded_client_errors: int | None,
) -> dict[str, Any]:
    bad_events = total_events - good_events
    availability = good_events / total_events * 100.0 if total_events else None
    allowed_bad_events = total_events * max(0.0, 100.0 - target) / 100.0
    if total_events == 0:
        budget_consumed = None
        budget_remaining = None
        burn_rate = None
        measurement_state = "no_data"
        within_objective = None
    elif allowed_bad_events == 0:
        budget_consumed = None
        budget_remaining = None
        burn_rate = None
        measurement_state = "measured"
        within_objective = bad_events == 0
    else:
        budget_consumed = bad_events / allowed_bad_events * 100.0
        budget_remaining = max(0.0, 100.0 - budget_consumed)
        burn_rate = bad_events / total_events / ((100.0 - target) / 100.0)
        measurement_state = "measured"
        within_objective = availability is not None and availability >= target
    result = {
        **MetricsRegistry.SLI_DESCRIPTION,
        "window_minutes": window_minutes,
        "target_percent": target,
        "availability_percent": (
            round(availability, 4) if availability is not None else None
        ),
        "good_events": good_events,
        "total_events": total_events,
        "bad_events": bad_events,
        "total_requests": total_events,
        "error_requests": bad_events,
        "error_budget_remaining_percent": (
            round(budget_remaining, 4) if budget_remaining is not None else None
        ),
        "error_budget_consumed_percent": (
            round(budget_consumed, 4) if budget_consumed is not None else None
        ),
        "burn_rate": round(burn_rate, 4) if burn_rate is not None else None,
        "within_objective": within_objective,
        "measurement_state": measurement_state,
        "source": source,
        "aggregation_scope": aggregation_scope,
    }
    if excluded_client_errors is not None:
        result["excluded_client_errors"] = excluded_client_errors
    return result


def _percentile(values: Iterable[float], fraction: float) -> float:
    ordered = list(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _format_number(value: float) -> str:
    return format(value, ".15g")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**values: str) -> str:
    return ",".join(f'{key}="{_escape(value)}"' for key, value in values.items())
