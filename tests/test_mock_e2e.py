"""End-to-end test against the scripted mock model (no real API key).

Runs the full BriefMinion workflow — research tools, subagent digest,
structured-output compose, approval-gated save, follow-up ask — against a
local OpenAI-compatible server that returns scripted replies. The news
search and article fetches are real (live Bing News RSS); only the model
is mocked.
"""

import json
import subprocess
import sys

import pytest

from briefminion.agent import run_ask, run_brief

from .mock_provider import MockModelServer


def _make_mock_config(tmp_path, server):
    """Generate a valid base config with the CLI, then add the mock provider."""
    subprocess.run(
        [sys.executable, "-m", "openminion", "config", "init", "--provider", "echo"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=120,
    )
    config_path = tmp_path / ".openminion" / "agents.json"
    config = json.loads(config_path.read_text())
    # Provider names must be one of the SDK's supported set, so the mock
    # rides the "openai" slot with a local base URL (the same mechanism as
    # the custom-openai-compatible preset).
    config["providers"]["openai"] = {
        "api_key": "",
        "api_key_env": "MOCK_API_KEY",
        "base_url": server.base_url,
        "http_connection_reuse_enabled": True,
        "max_tokens": 0,
        "model": "mock-model",
        "provider_identity": {},
        "temperature": 0.2,
        "timeout_seconds": 60,
        "tool_call_strategy": "native",
    }
    config["agents"]["mock"] = {
        "default_channel": "console",
        "name": "mock",
        "provider": "openai",
        "role": "",
        "system_prompt": "",
        "thinking": "",
    }
    # Multi-agent configs must name a default_agent explicitly, even when
    # the Agent is constructed with an explicit agent_id.
    config["default_agent"] = "mock"
    config["brain"] = {"auto_fact_extraction": {"enabled": False}}
    config_path.write_text(json.dumps(config))
    return str(config_path)


@pytest.fixture(scope="module")
def mock_server():
    server = MockModelServer()
    server.start()
    yield server
    server.stop()


def test_full_brief_workflow_against_mock_model(tmp_path, mock_server, monkeypatch):
    monkeypatch.setenv("MOCK_API_KEY", "mock-local-test-key")
    # OpenMinion builds httpx.Client(trust_env=True); the sandbox's default
    # NO_PROXY contains bracketed IPv6 entries that httpx 0.28.1 cannot
    # parse ("Invalid port: ':1]'"), so simplify it for the run.
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    config_path = _make_mock_config(tmp_path, mock_server)
    out_dir = tmp_path / "briefs"

    record = run_brief(
        topic="decentralized AI inference",
        agent_id="mock",
        config_path=config_path,
        out_dir=str(out_dir),
        max_sources=3,
        auto_approve=True,
    )

    assert record["fallbacks"] == []
    assert record["articles_fetched"] >= 1
    brief_path = record["saved_path"]
    text = open(brief_path, encoding="utf-8").read()
    assert text.startswith("# Research brief: decentralized AI inference")
    assert "## Summary" in text
    assert "## Key points" in text
    assert "## Sources" in text
    assert "http" in text  # at least one source link

    tool_names_seen = {
        name for entry in mock_server.requests_log for name in entry["tools"]
    }
    assert "search_news" in tool_names_seen
    assert "fetch_article" in tool_names_seen
    assert "save_brief" in tool_names_seen
    # Source links must be clean URLs: tool results arrive JSON-enveloped,
    # and an unwrapped parse would leak literal "\n" escapes into them.
    assert "\\n" not in text
    # The auto_fact_extraction flag does NOT stop the memory extractor in
    # 0.1.22: submit_output turns still fire (see BUILDING_BLOCKS.md).
    # The run must succeed anyway.
    extractor_calls = sum(
        1
        for entry in mock_server.requests_log
        if entry["tools"] == ["submit_output"]
    )
    assert extractor_calls >= 1

    answer = run_ask(
        question="What is the most important point?",
        topic="decentralized AI inference",
        agent_id="mock",
        config_path=config_path,
    )
    assert answer.strip()


def test_mock_server_returns_scripted_tool_calls(mock_server):
    import urllib.request

    payload = json.dumps(
        {
            "model": "mock-model",
            "stream": True,
            "messages": [{"role": "user", "content": "Research this topic: test"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_news",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        }
    ).encode()
    request = urllib.request.Request(
        f"{mock_server.base_url}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode()
    assert "search_news" in body
    assert "tool_calls" in body
    assert "[DONE]" in body
