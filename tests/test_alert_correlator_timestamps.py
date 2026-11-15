from datetime import datetime, timezone

from src.ml.alert_correlator import AlertCorrelator


def _alert(alert_id, timestamp=None):
    alert = {"id": alert_id, "name": "CPU alert", "message": "CPU usage high"}
    if timestamp is not None:
        alert["timestamp"] = timestamp
    return alert


def test_group_by_time_normalizes_mixed_datetime_representations():
    correlator = AlertCorrelator()
    alerts = [
        _alert("offset", "2026-11-15T13:00:00+01:00"),
        _alert("naive", datetime(2026, 11, 15, 12, 0)),
        _alert("utc", datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)),
    ]

    groups = correlator._group_by_time(alerts)

    assert [[alert["id"] for alert in group] for group in groups] == [
        ["offset", "naive", "utc"]
    ]


def test_group_by_time_keeps_invalid_timestamps_out_of_time_groups():
    correlator = AlertCorrelator()
    valid = _alert("valid", "2026-11-15T12:00:00Z")
    valid_peer = _alert("valid-peer", "2026-11-15T12:01:00Z")
    invalid = _alert("invalid", "not-a-timestamp")

    groups = correlator._group_by_time([invalid, valid, valid_peer])

    assert [[alert["id"] for alert in group] for group in groups] == [
        ["valid", "valid-peer"],
        ["invalid"],
    ]
    assert [alert["id"] for group in groups if len(group) == 1 for alert in group] == [
        "invalid"
    ]


def test_group_by_time_accepts_missing_timestamp_without_losing_alert():
    correlator = AlertCorrelator()

    groups = correlator._group_by_time([_alert("missing")])

    assert groups == [[_alert("missing")]]
