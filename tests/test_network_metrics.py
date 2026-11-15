from datetime import datetime
from types import SimpleNamespace

import psutil

from src.monitoring.system_monitor import SystemMonitor


def _network_io():
    return SimpleNamespace(
        bytes_sent=100,
        bytes_recv=200,
        packets_sent=3,
        packets_recv=4,
    )


def test_network_io_metrics_survive_connection_permission_failure(monkeypatch):
    monkeypatch.setattr(psutil, "net_io_counters", _network_io)

    def denied_connections():
        raise psutil.AccessDenied(pid=123)

    monkeypatch.setattr(psutil, "net_connections", denied_connections)

    metrics = SystemMonitor()._collect_network_metrics(datetime(2026, 1, 1))

    assert {metric["name"] for metric in metrics} == {
        "network_bytes_sent_total",
        "network_bytes_recv_total",
        "network_packets_sent_total",
        "network_packets_recv_total",
    }
    assert [metric["value"] for metric in metrics] == [100, 200, 3, 4]


def test_network_collection_includes_connection_count_when_available(monkeypatch):
    monkeypatch.setattr(psutil, "net_io_counters", _network_io)
    monkeypatch.setattr(psutil, "net_connections", lambda: [object(), object()])

    metrics = SystemMonitor()._collect_network_metrics(datetime(2026, 1, 1))

    assert len(metrics) == 5
    connection_metric = next(
        metric for metric in metrics if metric["name"] == "network_connections_total"
    )
    assert connection_metric["value"] == 2


def test_connection_count_is_preserved_when_io_counters_are_unavailable(monkeypatch):
    monkeypatch.setattr(psutil, "net_io_counters", lambda: None)
    monkeypatch.setattr(psutil, "net_connections", lambda: [object()])

    metrics = SystemMonitor()._collect_network_metrics(datetime(2026, 1, 1))

    assert metrics == [
        {
            "name": "network_connections_total",
            "value": 1,
            "timestamp": datetime(2026, 1, 1),
            "unit": "connections",
            "source": "psutil",
            "labels": {"type": "network"},
        }
    ]
