"""Tests for retry/approval helpers (fake agent, no model needed)."""

import pytest
from openminion import ProviderError, TurnTimeoutError

from briefminion.agent import (
    _is_rate_limit,
    make_approval_callback,
    run_with_retry,
)


class FakeResult:
    text = "done"


class FakeAgent:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = 0

    def run(self, message, **kwargs):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return FakeResult()


def test_is_rate_limit_detects_429_and_quota():
    assert _is_rate_limit(ProviderError("slow down", code="429"))
    assert _is_rate_limit(ProviderError("quota exceeded", code="402"))
    assert not _is_rate_limit(ProviderError("bad key", code="401"))
    assert not _is_rate_limit(ProviderError("boom", code="500"))


def test_run_with_retry_retries_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr("briefminion.agent.time.sleep", lambda seconds: None)
    agent = FakeAgent([ProviderError("slow down", code="429")])
    result = run_with_retry(agent, "hi", log=lambda m: None)
    assert result.text == "done"
    assert agent.calls == 2


def test_run_with_retry_gives_up_after_backoff(monkeypatch):
    monkeypatch.setattr("briefminion.agent.time.sleep", lambda seconds: None)
    agent = FakeAgent([ProviderError("slow down", code="429")] * 10)
    with pytest.raises(ProviderError):
        run_with_retry(agent, "hi", log=lambda m: None)
    assert agent.calls == 4  # initial + 3 backoff retries


def test_run_with_retry_does_not_retry_auth_errors(monkeypatch):
    monkeypatch.setattr("briefminion.agent.time.sleep", lambda seconds: None)
    agent = FakeAgent([ProviderError("bad key", code="401")])
    with pytest.raises(ProviderError):
        run_with_retry(agent, "hi", log=lambda m: None)
    assert agent.calls == 1


def test_run_with_retry_retries_timeout_once(monkeypatch):
    monkeypatch.setattr("briefminion.agent.time.sleep", lambda seconds: None)
    agent = FakeAgent([TurnTimeoutError("timed out")])
    result = run_with_retry(agent, "hi", log=lambda m: None)
    assert result.text == "done"
    assert agent.calls == 2


def test_approval_callback_auto_approve():
    decide = make_approval_callback(auto_approve=True)
    assert decide("save_brief", {"filename": "x.md"}, "id-1") is True


def test_approval_callback_asks_and_accepts_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    decide = make_approval_callback(auto_approve=False)
    assert decide("save_brief", {"filename": "x.md"}, "id-1") is True


def test_approval_callback_asks_and_defaults_to_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    decide = make_approval_callback(auto_approve=False)
    assert decide("save_brief", {"filename": "x.md"}, "id-1") is False
