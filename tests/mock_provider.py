"""A scripted OpenAI-compatible model server for end-to-end tests.

The mock answers with deterministic, scripted replies driven by the
conversation history: it calls BriefMinion's tools in the right order
(search -> fetch -> fetch), returns a digest, returns valid Brief JSON,
and calls the approval-gated save tool. It lets the full agent workflow
run without any model API key.

This is test infrastructure only: it proves the SDK wiring, tool loop,
delegation, structured output, approval flow, and sessions work — it does
not prove anything about a real model's behaviour.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

URL_RE = re.compile(r"https?://[^\s\\]+")


def _unwrap_tool_content(content: str) -> str:
    """Unwrap OpenMinion's JSON tool-result envelope.

    Tool results arrive wrapped as
    {"status": "success", "summary": ..., "outputs": {"data": "<text>"}}.
    The inner text is JSON-escaped, so newlines show up as literal ``\\n``
    until the envelope is parsed. Return the inner data, or the raw content
    when it is not an envelope.
    """
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content
    if isinstance(parsed, dict):
        outputs = parsed.get("outputs") or {}
        data = outputs.get("data")
        if isinstance(data, str):
            return data
    return content


def _text_of(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return ""


def _tool_call_id_to_name(messages: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            if call.get("id") and function.get("name"):
                mapping[call["id"]] = function["name"]
    return mapping


def _tool_results(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return (tool name, result text) for each tool message, in order."""
    id_to_name = _tool_call_id_to_name(messages)
    results = []
    for message in messages:
        if message.get("role") == "tool":
            name = id_to_name.get(message.get("tool_call_id", ""), "")
            results.append((name, _unwrap_tool_content(_text_of(message))))
    return results


def _max_sources_from_system(messages: list[dict[str, Any]]) -> int:
    """Read the 'at most N' source cap from the system prompt."""
    for message in messages:
        if message.get("role") == "system":
            match = re.search(r"at most (\d+)", _text_of(message))
            if match:
                return int(match.group(1))
    return 3


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return _text_of(message)
    return ""


def _source_blocks(prompt: str) -> list[tuple[str, str, str]]:
    """Parse 'SOURCE: title\\nURL: url\\ntext' blocks from a digest prompt."""
    blocks = []
    for chunk in prompt.split("SOURCE: ")[1:]:
        lines = chunk.split("\n", 2)
        title = lines[0].strip() if lines else ""
        url = ""
        text = ""
        if len(lines) > 1 and lines[1].startswith("URL: "):
            url = lines[1][5:].strip()
        if len(lines) > 2:
            text = lines[2].strip()
        blocks.append((title, url, text))
    return blocks


class MockDecisions:
    """Decide the scripted reply for one chat-completions request."""

    def __init__(self) -> None:
        self.call_counter = 0

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return {"kind": "text", "text": ...} or {"kind": "tool", ...}."""
        messages = payload.get("messages") or []
        tools = [
            (item.get("function") or {}).get("name")
            for item in payload.get("tools") or []
        ]
        results = _tool_results(messages)
        last_user = _last_user_text(messages)
        result_names = [name for name, _ in results]

        if "submit_output" in tools:
            return {"kind": "text", "text": "No facts to extract."}

        if "search_news" in tools:
            if not results:
                topic = last_user.split("Research this topic:", 1)[-1].strip()
                return {
                    "kind": "tool",
                    "name": "search_news",
                    "arguments": {"topic": topic, "max_results": 4},
                }
            search_text = next(
                (text for name, text in results if name == "search_news"), ""
            )
            urls = URL_RE.findall(search_text)
            fetched = result_names.count("fetch_article")
            max_sources = _max_sources_from_system(messages)
            if fetched < max_sources and fetched < len(urls):
                return {
                    "kind": "tool",
                    "name": "fetch_article",
                    "arguments": {"url": urls[fetched]},
                }
            titles = [
                line.split("Article:", 1)[-1].strip().split("\n")[0]
                for name, text in results
                if name == "fetch_article"
                for line in text.split("\n")
                if line.startswith("Article:")
            ]
            listing = "; ".join(titles) if titles else "no articles"
            return {"kind": "text", "text": f"Fetched articles: {listing}."}

        if "save_brief" in tools:
            if not results:
                filename = last_user.split("filename ", 1)[-1].split(" ", 1)[0]
                content = last_user.split("markdown content:\n\n", 1)[-1]
                return {
                    "kind": "tool",
                    "name": "save_brief",
                    "arguments": {"filename": filename, "content": content},
                }
            return {"kind": "text", "text": "Brief saved."}

        if last_user.startswith("Distil these articles:"):
            blocks = _source_blocks(last_user)
            lines = ["Key facts:"]
            for title, _url, text in blocks:
                first_sentence = text.split(". ")[0].strip()
                lines.append(f"- {title}: {first_sentence[:160]}")
            return {"kind": "text", "text": "\n".join(lines)}

        if last_user.startswith("Write the research brief for:"):
            topic = last_user.split("for:", 1)[-1].split("\n")[0].strip()
            sources = []
            in_sources = False
            for line in last_user.split("\n"):
                if line.strip() == "Sources:":
                    in_sources = True
                    continue
                if in_sources and line.startswith("- "):
                    title, _, url = line[2:].partition(" | ")
                    sources.append(
                        {"title": title.strip(), "url": url.strip(), "published": ""}
                    )
            brief = {
                "title": f"Research brief: {topic}",
                "summary": (
                    f"Recent coverage of {topic} points to continued "
                    "activity across the sources reviewed for this brief."
                ),
                "key_points": [
                    f"Coverage of {topic} remains active.",
                    "Multiple independent sources report on the topic.",
                ],
                "timeline": [],
                "sources": sources,
            }
            return {"kind": "text", "text": json.dumps(brief)}

        return {
            "kind": "text",
            "text": "Mock answer based on the brief in this session.",
        }


def _sse_chunk(delta: dict[str, Any], finish_reason: str | None) -> bytes:
    payload = {
        "id": "chatcmpl-mock",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "mock-model",
        "choices": [
            {"index": 0, "delta": delta, "finish_reason": finish_reason}
        ],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


class MockModelServer:
    """Threaded HTTP server exposing the scripted mock model."""

    def __init__(self) -> None:
        self.decisions = MockDecisions()
        self.requests_log: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        assert self._server is not None
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:  # keep test output clean
                pass

            def do_GET(self) -> None:
                if self.path == "/v1/models":
                    body = json.dumps(
                        {"object": "list", "data": [{"id": "mock-model"}]}
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8") or "{}")
                messages = payload.get("messages") or []
                tools = [
                    (item.get("function") or {}).get("name")
                    for item in payload.get("tools") or []
                ]
                outer.requests_log.append(
                    {
                        "path": self.path,
                        "model": payload.get("model"),
                        "tools": tools,
                        "n_messages": len(messages),
                        "stream": bool(payload.get("stream")),
                    }
                )
                decision = outer.decisions.decide(payload)
                outer.decisions.call_counter += 1
                if payload.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    if decision["kind"] == "tool":
                        delta = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": f"call_mock_{outer.decisions.call_counter}",
                                    "type": "function",
                                    "function": {
                                        "name": decision["name"],
                                        "arguments": json.dumps(
                                            decision["arguments"]
                                        ),
                                    },
                                }
                            ],
                        }
                        self.wfile.write(_sse_chunk(delta, None))
                        self.wfile.write(_sse_chunk({}, "tool_calls"))
                    else:
                        self.wfile.write(
                            _sse_chunk(
                                {"role": "assistant", "content": decision["text"]},
                                None,
                            )
                        )
                        self.wfile.write(_sse_chunk({}, "stop"))
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    if decision["kind"] == "tool":
                        message = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"call_mock_{outer.decisions.call_counter}",
                                    "type": "function",
                                    "function": {
                                        "name": decision["name"],
                                        "arguments": json.dumps(decision["arguments"]),
                                    },
                                }
                            ],
                        }
                        finish = "tool_calls"
                    else:
                        message = {"role": "assistant", "content": decision["text"]}
                        finish = "stop"
                    body = json.dumps(
                        {
                            "id": "chatcmpl-mock",
                            "object": "chat.completion",
                            "created": 0,
                            "model": "mock-model",
                            "choices": [
                                {"index": 0, "message": message, "finish_reason": finish}
                            ],
                        }
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
