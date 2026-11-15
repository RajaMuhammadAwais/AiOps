from datetime import datetime, timezone

from src.ml.alert_correlator import AlertCorrelator


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
