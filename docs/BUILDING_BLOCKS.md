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
| `@tool` (read-only, idempotent) | `search_news`, `fetch_article` | Works (unit-tested; live run pending) |
| `@tool(dangerous=True)` + `approval_callback` | `save_brief` | Works (unit-tested; live run pending) |
| `forced_tools` | research + save phases | Works with a real model (pending live model); no-op under echo |
| `subagent()` bounded subagent | digest phase | Pending live model |
| `output_type` structured output | compose phase | Pending live model |
| Sessions (`session_id`, shared + follow-up) | brief + `ask` | Pending live model |
| `ProviderError` / `TurnTimeoutError` handling | retry wrapper | Works (unit-tested with fakes) |
| `openminion setup --provider ...` | provider config | Refuses without a credential (finding 4) |
| Cortensor Portal preset (`cortensor-portal`) | intended inference route | Config verified; live run pending key |
| Cortensor Router preset (`cortensor-router`) | not used | Needs a locally operated router node; out of scope |
| OpenRouter preset (`openrouter`) | dev + demo route | Config verified; live run pending key |

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

## Live-model runs (pending live model)

To be filled in after the OpenRouter-free and (if access is granted)
Portal runs: tool-call behaviour, subagent digest quality, structured
output validation, approval flow, session continuity for `ask`, turn
sizes, latency, and any rate limits hit.

## Test evidence

- `python -m pytest tests/ -q` → 24 passed (no model key needed).
- Echo-provider smoke test: `briefminion brief ... --agent openminion`
  fails cleanly with exit code 1 and "No articles could be fetched..."
  (expected: echo cannot call tools).
- Live network checks (in the test suite): Google News RSS returns items;
  plain article fetch works.
