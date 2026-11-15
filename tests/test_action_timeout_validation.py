import asyncio
from unittest.mock import Mock

import pytest

from src.alerting import alert_manager as alert_manager_module
from src.alerting.alert_manager import ActionType, AlertManager, SelfHealingAction
from src.automation import intelligent_orchestrator as orchestrator_module
from src.automation.intelligent_orchestrator import IntelligentOrchestrator


class _SuccessfulResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"success": True}


@pytest.mark.parametrize("timeout", [True, False])
def test_alert_manager_rejects_boolean_timeout_without_request(monkeypatch, timeout):
    post = Mock()
    monkeypatch.setattr(alert_manager_module.requests, "post", post)
    manager = AlertManager(executor_url="https://executor.test")
    action = SelfHealingAction(
        id="action-1",
        name="test-action",
        action_type=ActionType.ALERT_TEAM,
        condition="",
        parameters={"timeout_seconds": timeout},
    )

    result = manager._dispatch(action, {"id": "alert-1"})

    assert result["success"] is False
    post.assert_not_called()


@pytest.mark.parametrize("timeout", [True, False])
def test_orchestrator_rejects_boolean_timeout_without_request(monkeypatch, timeout):
    post = Mock()
    monkeypatch.setattr(orchestrator_module.requests, "post", post)
    orchestrator = IntelligentOrchestrator(executor_url="https://executor.test")

    result = asyncio.run(
        orchestrator._execute_orchestrated_action(
            {"type": "test-action", "parameters": {"timeout_seconds": timeout}},
            {},
        )
    )

    assert result["success"] is False
    post.assert_not_called()


@pytest.mark.parametrize("timeout", [2, 2.5])
def test_alert_manager_preserves_valid_numeric_timeout(monkeypatch, timeout):
    post = Mock(return_value=_SuccessfulResponse())
    monkeypatch.setattr(alert_manager_module.requests, "post", post)
    manager = AlertManager(executor_url="https://executor.test")
    action = SelfHealingAction(
        id="action-1",
        name="test-action",
        action_type=ActionType.ALERT_TEAM,
        condition="",
        parameters={"timeout_seconds": timeout},
    )

    result = manager._dispatch(action, {"id": "alert-1"})

    assert result["success"] is True
    assert post.call_args.kwargs["timeout"] == float(timeout)


@pytest.mark.parametrize("timeout", [2, 2.5])
def test_orchestrator_preserves_valid_numeric_timeout(monkeypatch, timeout):
    post = Mock(return_value=_SuccessfulResponse())
    monkeypatch.setattr(orchestrator_module.requests, "post", post)
    orchestrator = IntelligentOrchestrator(executor_url="https://executor.test")

    result = asyncio.run(
        orchestrator._execute_orchestrated_action(
            {"type": "test-action", "parameters": {"timeout_seconds": timeout}},
            {},
        )
    )

    assert result["success"] is True
    assert post.call_args.kwargs["timeout"] == float(timeout)
