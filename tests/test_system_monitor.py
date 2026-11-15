from datetime import datetime
from types import SimpleNamespace

import psutil

from src.monitoring.system_monitor import SystemMonitor


def _process(pid, name, cpu_percent, memory_percent=None):
    info = {
        "pid": pid,
        "name": name,
        "cpu_percent": cpu_percent,
    }
    if memory_percent is not None:
        info["memory_percent"] = memory_percent
    return SimpleNamespace(info=info)


def test_process_metrics_include_top_five_processes_by_memory(monkeypatch):
    processes = [
        _process(1, "p1", 99, 10),
        _process(2, "p2", 20, 90),
        _process(3, "p3", 80, 70),
        _process(4, "p4", 10, 50),
        _process(5, "p5", 60, 30),
        _process(6, "p6", 30, 80),
    ]
    monkeypatch.setattr(
        psutil, "pids", lambda: [item.info["pid"] for item in processes]
    )
    monkeypatch.setattr(psutil, "process_iter", lambda _attrs: iter(processes))

    metrics = SystemMonitor()._collect_process_metrics(datetime(2026, 1, 1))
    memory_metrics = [
        metric for metric in metrics if metric["name"].startswith("top_memory_process_")
    ]

    assert [metric["value"] for metric in memory_metrics] == [90, 80, 70, 50, 30]
    assert [metric["labels"]["rank"] for metric in memory_metrics] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert [metric["labels"]["process_name"] for metric in memory_metrics] == [
        "p2",
        "p6",
        "p3",
        "p4",
        "p5",
    ]
    assert all(metric["unit"] == "percent" for metric in memory_metrics)


def test_process_memory_metrics_handle_fewer_processes_and_missing_values(
    monkeypatch,
):
    processes = [
        _process(1, "known", 5, 55),
        SimpleNamespace(
            info={
                "pid": 2,
                "name": "unavailable",
                "cpu_percent": 90,
                "memory_percent": None,
            }
        ),
        _process(3, "missing", 10),
    ]
    monkeypatch.setattr(psutil, "pids", lambda: [1, 2, 3])
    monkeypatch.setattr(psutil, "process_iter", lambda _attrs: iter(processes))

    metrics = SystemMonitor()._collect_process_metrics(datetime(2026, 1, 1))
    memory_metrics = [
        metric for metric in metrics if metric["name"].startswith("top_memory_process_")
    ]

    assert len(memory_metrics) == 3
    assert [metric["value"] for metric in memory_metrics] == [55, 0, 0]
    assert [metric["labels"]["process_name"] for metric in memory_metrics] == [
        "known",
        "unavailable",
        "missing",
    ]
