import asyncio
import json

from src.chatops.llm_assistant import LLMRequestError, LLMAssistant

ALERT = {
    "name": "High CPU",
    "severity": "critical",
    "message": "CPU exceeded threshold",
}


def _assistant():
    assistant = LLMAssistant.__new__(LLMAssistant)
    assistant.client = object()
    assistant.model = "test-model"
    return assistant


def test_transport_failure_is_unavailable_without_prediction(monkeypatch):
    assistant = _assistant()

    async def failed_request(_prompt):
        raise LLMRequestError("request failed: HTTP 503")

    monkeypatch.setattr(assistant, "_make_openai_request", failed_request)

    result = asyncio.run(assistant.explain_incident(ALERT, []))

    assert result["analysis_status"] == "unavailable"
    assert result["predicted_time"] is None
    assert "HTTP 503" in result["explanation"]


def test_malformed_model_output_never_creates_prediction(monkeypatch):
    assistant = _assistant()

    async def malformed_request(_prompt):
        return "not valid JSON"

    monkeypatch.setattr(assistant, "_make_openai_request", malformed_request)

    result = asyncio.run(assistant.explain_incident(ALERT, []))

    assert result["analysis_status"] == "invalid_response"
    assert result["predicted_time"] is None
    assert result["explanation"] == "not valid JSON"


def test_valid_structured_model_output_preserves_prediction(monkeypatch):
    assistant = _assistant()
    expected = {
        "description": "CPU saturation",
        "explanation": "The host is CPU constrained.",
        "root_cause": "Workload increase",
        "predicted_time": 12,
    }

    async def valid_request(_prompt):
        return json.dumps(expected)

    monkeypatch.setattr(assistant, "_make_openai_request", valid_request)

    result = asyncio.run(assistant.explain_incident(ALERT, []))

    assert result == expected
