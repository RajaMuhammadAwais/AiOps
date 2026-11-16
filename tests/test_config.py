from unittest.mock import patch
import os

import pytest

from src.platform.config import ConfigurationError, Settings

BASE_ENV = {
    "AIOPS_ENV": "test",
    "AIOPS_SERVICE_NAME": "aiops-test",
    "AIOPS_VERSION": "test-version",
    "AIOPS_LOG_LEVEL": "INFO",
    "AIOPS_PROMETHEUS_TIMEOUT_SECONDS": "5",
    "AIOPS_VERIFY_TLS": "true",
    "AIOPS_MAX_QUERY_LENGTH": "2000",
    "AIOPS_RATE_LIMIT_PER_MINUTE": "120",
    "AIOPS_AUDIT_LOG_MAX_ENTRIES": "5000",
    "AIOPS_EVENT_STORE_MAX_ENTRIES": "1000",
    "AIOPS_SLO_TARGET": "99.5",
    "AIOPS_SLO_WINDOW_MINUTES": "60",
    "AIOPS_REFRESH_SECONDS": "30",
    "AIOPS_HOST": "127.0.0.1",
    "AIOPS_PORT": "5000",
}


def test_approval_url_and_service_key_must_be_configured_together():
    for values in (
        BASE_ENV | {"AIOPS_APPROVAL_URL": "https://approval.example/verify"},
        BASE_ENV | {"AIOPS_APPROVAL_API_KEY": "a" * 24},
    ):
        with patch.dict(os.environ, values, clear=True):
            with pytest.raises(ConfigurationError, match="must be configured together"):
                Settings.from_env()


def test_approval_service_key_requires_minimum_length():
    values = BASE_ENV | {
        "AIOPS_APPROVAL_URL": "https://approval.example/verify-and-consume",
        "AIOPS_APPROVAL_API_KEY": "too-short",
    }
    with patch.dict(os.environ, values, clear=True):
        with pytest.raises(ConfigurationError, match="AIOPS_APPROVAL_API_KEY"):
            Settings.from_env()


def test_approval_endpoint_requires_https():
    values = BASE_ENV | {
        "AIOPS_APPROVAL_URL": "http://approval.example/verify-and-consume",
        "AIOPS_APPROVAL_API_KEY": "a" * 24,
    }
    with patch.dict(os.environ, values, clear=True):
        with pytest.raises(ConfigurationError, match="must use HTTPS"):
            Settings.from_env()


def test_approval_endpoint_cannot_embed_credentials_or_query_tokens():
    for url in (
        "https://user:password@approval.example/verify-and-consume",
        "https://approval.example/verify-and-consume?token=secret",
        "https://approval.example/verify-and-consume#fragment",
    ):
        values = BASE_ENV | {
            "AIOPS_APPROVAL_URL": url,
            "AIOPS_APPROVAL_API_KEY": "a" * 24,
        }
        with patch.dict(os.environ, values, clear=True):
            with pytest.raises(ConfigurationError, match="must use HTTPS"):
                Settings.from_env()


def test_valid_approval_configuration_is_loaded():
    values = BASE_ENV | {
        "AIOPS_APPROVAL_URL": "https://approval.example/verify-and-consume",
        "AIOPS_APPROVAL_API_KEY": "a" * 24,
    }
    with patch.dict(os.environ, values, clear=True):
        settings = Settings.from_env()

    assert settings.approval_url == values["AIOPS_APPROVAL_URL"]
    assert settings.approval_api_key == values["AIOPS_APPROVAL_API_KEY"]
