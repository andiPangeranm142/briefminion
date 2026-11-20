# Building Blocks Tested

What BriefMinion exercised in the OpenMinion 0.1.22 Python SDK, what worked,
and what did not. Every claim here was observed while building this project
on Python 3.12.3 (Linux) between 20–26 Nov 2026.

> Status: this note is updated as testing proceeds. Sections marked
> **(pending live model)** need a model API key and are completed once the
> live runs are done.

## Summary

| Building block | Used by BriefMinion | Verdict |
| --- | --- | --- |
| Install + CLI (`openminion==0.1.22`) | setup, doctor, config | Works |
| `config init --provider echo` | local bring-up | Works, with a docs mismatch (finding 2) |
| Echo provider | wiring smoke tests | Works for wiring only; silently skips tools (finding 3) |
| `Agent` (context manager) + `agent.run()` | all four phases | Works |
| `@tool` (read-only, idempotent) | `search_news`, `fetch_article` | Works (unit-tested + mock end-to-end; live model pending) |
| `@tool(dangerous=True)` + `approval_callback` | `save_brief` | Works (unit-tested + mock end-to-end; live model pending) |
| `forced_tools` | research + save phases | Works with a real model (pending live model); no-op under echo |
| `subagent()` bounded subagent | digest phase | Works (mock end-to-end; live model pending) |
| `output_type` structured output | compose phase | Works (mock end-to-end; live model pending) |
| Sessions (`session_id`, shared + follow-up) | brief + `ask` | Works (mock end-to-end; live model pending) |
| `ProviderError` / `TurnTimeoutError` handling | retry wrapper | Works (unit-tested with fakes) |
| `openminion setup --provider ...` | provider config | Refuses without a credential (finding 4) |
| Cortensor Portal preset (`cortensor-portal`) | intended inference route | Config verified; live run pending key |
| Cortensor Router preset (`cortensor-router`) | not used | Needs a locally operated router node; out of scope |
| OpenRouter preset (`openrouter`) | dev + demo route | Config verified; live run pending key |
| Mock OpenAI-compatible provider | end-to-end tests | Works via the `openai` slot + local base URL |

## Findings

### 1. Install is clean (works)
`pip install openminion==0.1.22` on Python 3.12.3 installs without errors;
`openminion --version` reports 0.1.22 and the SDK imports cleanly.
The `@tool` decorator returns a plain callable function (with
`tool_args_model` / `tool_decl` attributes attached), so tools are directly
unit-testable without a model — genuinely good design for a hackathon
build. All 24 of our pytest tests run without any model key.

### 2. `config init` creates agent `openminion`, docs say `default` (rough edge)
`openminion config init --provider echo` writes project-scoped
`.openminion/agents.json` (mode 600) with a single agent id `openminion`
and `default_agent: null`. The SDK docs and `provider_switching.py`
example use `--agent default`, which does not exist after init. A first-time
builder following the docs hits a confusing "unknown agent" failure.
Pick one id and update the docs/examples to match.

### 3. Echo provider silently ignores `forced_tools` (rough edge)
Running the SDK's own `tool_agent.py` example against the echo provider
returns only the echoed prompt — the forced `lookup_order` tool never
executes, with no warning. Echo therefore validates Agent wiring only, not
tool behaviour. A warning ("echo provider cannot execute tools") would
save builders a confusing half hour.

### 4. `setup` refuses to write config without a credential (rough edge)
`openminion setup --provider openrouter --model ... --no-chat` fails with
"Setup failed: Missing credential for OpenRouter" when the env var is
absent — even though the docs say setup "does not prove account access".
Builders cannot pre-configure a provider (e.g. in CI, or before a key
arrives). Warn and write the config instead of failing.

### 5. Cortensor Portal gateway is live and healthy (works, key required)
Probed 20 Nov 2026 without a key: `GET /health` → 200;
`GET /v1/models` → 401 with a clear `missing_api_key` error;
`GET /public/stats/summary` → 200, status "healthy", but the stats were
stale (~22.6 h old) with `requests_total: 2` in the last 24 h — the
gateway works, but barely anyone is using it yet.

### 6. Portal tool-call support: CLI and docs contradict each other (unresolved)
The 0.1.22 CLI (`setup --list-providers`) describes `cortensor-portal`
as supporting "experimental hosted text, streaming, and native tool
calls", while the Cortensor docs (last updated 2026-07-13) state
"Tool/function calling is not exposed on the hosted compatibility
routes." Only a live keyed run resolves this; see the live-run section
below once Portal access is available.

### 7. Hackathon #5 submission repo is still unpublished (process finding)
The hackathon docs (last updated 2026-10-07) still say "The repository
URL will be added before kickoff", and neither the `cortensor` nor the
`OpenMinion` GitHub org lists a Hackathon #5 submissions repository
(checked 20 Nov 2026). Builders cannot confirm the exact PR destination
from public sources; the live DoraHacks page / Discord announcement is
the only authority left.

### 8. Multi-agent configs require an explicit `default_agent` (rough edge)
Adding a second agent to `agents.json` makes every `Agent(...)`
construction fail with `UnknownProfileError: multi-agent config requires
explicit 'default_agent'` — even when the Agent is constructed with an
explicit `agent_id`. The default is resolved before the explicit choice
is considered. Setting `"default_agent"` fixes it, but the requirement is
surprising when the caller already named the agent.

### 9. Provider names are restricted to the built-in set (rough edge)
A provider block under a custom name (e.g. `"mock"`) is rejected by the
provider factory: `Unknown provider 'mock'. Supported: anthropic,
cerebras, claude, cortensor, echo, groq, ollama, openai, openrouter`.
Local/test endpoints must ride the `openai` slot with a custom
`base_url` (the same mechanism as the `custom-openai-compatible`
preset). That works — our whole end-to-end test uses it — but a custom
name would be clearer.

### 10. httpx breaks on bracketed-IPv6 `NO_PROXY` entries (environment finding)
OpenMinion's transport builds `httpx.Client(trust_env=True)`. In our
sandbox the default `NO_PROXY` contains bracketed IPv6 entries
(`[::1]`, `[fd8b:...]`), and httpx 0.28.1 fails to parse them:
`InvalidURL: Invalid port: ':1]'` — at client construction, before any
request is sent. Every provider call fails. Workaround: run with a
simplified `NO_PROXY=localhost,127.0.0.1`. (Upstream httpx parsing
behaviour, but the SDK could sanitise proxy env or set
`trust_env=False` with explicit proxy support.)

### 11. Tool results arrive wrapped in a JSON envelope (works, with a cost)
A tool's return value reaches the model wrapped as
`{"status": "success", "summary": "Tool executed successfully",
"outputs": {"data": "<the actual text>"}}`. The model must look inside
`outputs.data`, and the envelope adds tokens to every tool round trip.
The inner text is JSON-escaped, so naive parsing of the raw content (as
our first mock did) misreads newlines. Document the envelope shape so
builders — and local test harnesses — parse tool results correctly.

### 12. The `auto_fact_extraction` flag does not stop the extractor (bug)
Setting top-level `"brain": {"auto_fact_extraction": {"enabled": false}}`
in `agents.json` (the known workaround, and the config system does parse
it into `module_configs.brain`) did **not** stop the memory extractor:
in one mock brief run, 12 of 23 model requests were `submit_output`
extractor turns, each an extra round trip. On a paced free tier that is
real cost. Either the flag is ignored in 0.1.22 or it gates something
else; either way the behaviour contradicts the workaround.

### 13. First request of a turn exposes only the forced tools (behaviour)
With `forced_tools=["search_news"]`, the turn's first model request
lists only `search_news`; the full tool list appears from the second
request onward. Harmless once known, confusing while debugging (it looks
like the other tools failed to register).

### 14. `Agent.run` uses non-streaming requests (behaviour)
Despite the adapter's SSE streaming support, SDK `Agent.run` turns send
`"stream": false`. Streaming appears to be a CLI/chat path. Fine for a
Python agent, but worth knowing when building a local test provider.

### 15. Google News RSS rate-limits repeated calls (data-source note)
After ~15 RSS calls in an hour from one egress IP, the feed answered
HTTP 429. BriefMinion's fetcher retries 429/503 with backoff
(10s / 25s / 60s); the agent also retries the tool call through the
normal turn loop. A production deployment would want a cache.

## Mock end-to-end run (completed 20 Nov 2026)

The full workflow ran against a local scripted OpenAI-compatible server
(`tests/mock_provider.py`): research tools (3 real articles fetched from
live RSS), subagent digest, structured-output compose, approval-gated
save, and a follow-up `ask` in the same session — 0 fallbacks, brief
saved with all sections, 23 model requests. This proves the SDK wiring
end to end; it does not prove real-model behaviour.

## Live-model runs (pending live model)

To be filled in after the OpenRouter-free and (if access is granted)
Portal runs: tool-call behaviour, subagent digest quality, structured
output validation, approval flow, session continuity for `ask`, turn
sizes, latency, and any rate limits hit.

## Test evidence

- `python -m pytest tests/ -q` → 28 passed (24 unit + 2 retry + 2 mock
  end-to-end). No model key needed.
- Mock end-to-end: full brief workflow against a scripted local model
  (see above) — 3 articles, 0 fallbacks, brief + run log saved.
- Echo-provider smoke test: `briefminion brief ... --agent openminion`
  fails cleanly with exit code 1 and "No articles could be fetched..."
  (expected: echo cannot call tools).
- Live network checks (in the test suite): Google News RSS returns items;
  plain article fetch works.
