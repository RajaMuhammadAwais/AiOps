import asyncio

import pytest
from click.testing import CliRunner

from src.cli import aiops_cli


class FakeSystemMonitor:
    def __init__(self):
        self.monitoring_interval = 0.001
        self.collect_calls = 0
        self.collection_cancelled = False

    async def collect_metrics(self):
        self.collect_calls += 1
        return []


class FakeAnomalyDetector:
    @staticmethod
    def detect_anomalies(_metrics):
        return []


def _controller():
    controller = aiops_cli.AIOpsController.__new__(aiops_cli.AIOpsController)
    controller.system_monitor = FakeSystemMonitor()
    controller.anomaly_detector = FakeAnomalyDetector()
    return controller


def test_monitor_command_passes_duration_to_controller(monkeypatch):
    received = []

    class StubController:
        async def start_monitoring(self, duration_minutes=0):
            received.append(duration_minutes)

    monkeypatch.setattr(aiops_cli, "AIOpsController", StubController)
    result = CliRunner().invoke(aiops_cli.cli, ["monitor", "--duration", "7"])

    assert result.exit_code == 0, result.output
    assert received == [7]


def test_monitor_command_rejects_negative_duration(monkeypatch):
    monkeypatch.setattr(aiops_cli, "AIOpsController", lambda: object())
    result = CliRunner().invoke(aiops_cli.cli, ["monitor", "--duration", "-1"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output


def test_zero_duration_keeps_monitoring_until_cancelled(monkeypatch):
    controller = _controller()
    original_sleep = asyncio.sleep
    sleep_calls = 0

    async def cancel_after_two_cycles(_delay):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 2:
            raise asyncio.CancelledError
        await original_sleep(0)

    monkeypatch.setattr(aiops_cli.asyncio, "sleep", cancel_after_two_cycles)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(controller.start_monitoring(duration_minutes=0))

    assert controller.system_monitor.collect_calls == 2
    assert sleep_calls == 2


def test_positive_duration_stops_at_monotonic_deadline(monkeypatch):
    controller = _controller()
    clock_values = iter([10.0, 10.0, 70.0, 70.0])
    monkeypatch.setattr(aiops_cli, "monotonic", lambda: next(clock_values))

    asyncio.run(controller.start_monitoring(duration_minutes=1))

    assert controller.system_monitor.collect_calls == 1


def test_duration_expiry_cancels_in_flight_collection(monkeypatch):
    controller = _controller()

    async def collect_until_cancelled():
        try:
            await asyncio.Future()
        finally:
            controller.system_monitor.collection_cancelled = True

    controller.system_monitor.collect_metrics = collect_until_cancelled
    original_sleep = asyncio.sleep

    async def expire_and_cancel(awaitable, timeout):
        assert timeout > 0
        task = asyncio.create_task(awaitable)
        await original_sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        raise asyncio.TimeoutError

    monkeypatch.setattr(aiops_cli.asyncio, "wait_for", expire_and_cancel)

    asyncio.run(controller.start_monitoring(duration_minutes=1))

    assert controller.system_monitor.collection_cancelled
