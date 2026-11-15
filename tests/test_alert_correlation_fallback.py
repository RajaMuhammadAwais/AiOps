from datetime import datetime, timezone

from src.ml.alert_correlator import AlertCorrelator
from src.models.incident import Alert, AlertSource, IncidentSeverity


def _alerts(name, message, count=11):
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "id": f"alert-{index}",
            "name": name,
            "message": message,
            "severity": "critical",
            "timestamp": timestamp,
            "labels": {},
        }
        for index in range(count)
    ]


def test_vectorizer_failure_does_not_correlate_or_suppress_alerts():
    alerts = _alerts("the", "a")

    result = AlertCorrelator().correlate_alerts(alerts)

    assert result["correlated_groups"] == []
    assert result["suppressed_alerts"] == []
    assert [alert["id"] for alert in result["unique_alerts"]] == [
        alert["id"] for alert in alerts
    ]


def test_empty_alert_text_does_not_create_a_synthetic_noise_group():
    alerts = _alerts("", "")

    result = AlertCorrelator().correlate_alerts(alerts)

    assert result["correlated_groups"] == []
    assert result["suppressed_alerts"] == []
    assert [alert["id"] for alert in result["unique_alerts"]] == [
        alert["id"] for alert in alerts
    ]


def test_pydantic_alert_serializes_to_correlator_contract():
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    alert = Alert(
        id="alert-model-1",
        name="CPU anomaly",
        severity=IncidentSeverity.HIGH,
        source=AlertSource.SYSTEM,
        timestamp=timestamp,
        message="CPU exceeded threshold",
        labels={"service": "api"},
        metrics=[{"metric_name": "cpu", "value": 97.5}],
    )

    result = AlertCorrelator().correlate_alerts([alert.model_dump(mode="json")])

    serialized = result["unique_alerts"][0]
    assert serialized["id"] == alert.id
    assert serialized["severity"] == alert.severity.value
    assert serialized["timestamp"] == timestamp.isoformat().replace("+00:00", "Z")
    assert serialized["labels"] == alert.labels
    assert serialized["metrics"] == alert.metrics
