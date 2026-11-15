import json

from src.ml.alert_correlator import AlertCorrelator


def test_pattern_returns_only_labels_shared_by_every_alert_as_json_values():
    correlator = AlertCorrelator()
    alerts = [
        {"labels": {"service": "api", "region": "west", "env": "prod"}},
        {"labels": {"service": "api", "region": "west", "env": "stage"}},
        {"labels": {"service": "api", "region": "west"}},
    ]

    pattern = correlator._extract_pattern(alerts)

    assert pattern["common_labels"] == {"service": "api", "region": "west"}
    json.dumps(pattern)


def test_pattern_excludes_conflicting_label_values():
    correlator = AlertCorrelator()
    alerts = [
        {"labels": {"service": "api", "region": "west"}},
        {"labels": {"service": "api", "region": "east"}},
    ]

    pattern = correlator._extract_pattern(alerts)

    assert pattern["common_labels"] == {"service": "api"}
    json.dumps(pattern)
