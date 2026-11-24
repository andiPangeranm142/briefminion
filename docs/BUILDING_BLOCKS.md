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
| `@tool` (read-only, idempotent) | `search_news`, `fetch_article` | Works live (30 calls in probe 2; per-run budgets added after the loop — finding 19) |
| `@tool(dangerous=True)` + `approval_callback` | `save_brief` | Works (unit-tested + mock end-to-end; live model pending) |
| `forced_tools` | research + save phases | Works live (search forced first in probe 2) |
| `subagent()` bounded subagent | digest phase | Works (mock end-to-end; live model pending — probe 2 never reached it) |
| `output_type` structured output | compose phase | Works (mock end-to-end; live model pending) |
| Sessions (`session_id`, shared + follow-up) | brief + `ask` | Works (mock end-to-end; live model pending) |
| `ProviderError` / `TurnTimeoutError` handling | retry wrapper | Works (unit-tested with fakes) |
| `openminion setup --provider ...` | provider config | Refuses without a credential (finding 4) |
| Cortensor Portal preset (`cortensor-portal`) | intended inference route | Config verified; live run pending key |
| Cortensor Router preset (`cortensor-router`) | not used | Needs a locally operated router node; out of scope |
| OpenRouter preset (`openrouter`) | dev + demo route | Live probes done (findings 16–19); full run pending quota reset |
| Mock OpenAI-compatible provider | end-to-end tests | Works via the `openai` slot + local base URL |

## Findings

### 1. Install is clean (works)
`pip install openminion==0.1.22` on Python 3.12.3 installs without errors;
`openminion --version` reports 0.1.22 and the SDK imports cleanly.
The `@tool` decorator returns a plain callable function (with
`tool_args_model` / `tool_decl` attributes attached), so tools are directly
unit-testable without a model — genuinely good design for a hackathon
build. All 33 of our pytest tests run without any model key.

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
`{"status": "success", "summary": ..., "outputs": {...}}`. For a tool
that returns a string, `outputs` is `{"data": "<the actual text>"}` and
the inner text is JSON-escaped, so naive parsing of the raw content (as
our first mock did) misreads newlines. For a tool that returns a dict,
the dict is spread **directly into `outputs`** (no `data` key) and
`summary` holds the dict's JSON string. Document the envelope shape so
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

### 16. The default per-conversation token budget exhausts mid-research (bug)
The SDK's default budget is 100,000 tokens per conversation
(`_default_budgets`, `max_total_llm_tokens=100_000` in
`services/brain/constants.py`), and the SDK's own per-request context
packing consumes ~12k estimated tokens for a trivial turn (a smoke test
that only said "SMOKE-OK" moved the budget 100,000 → 87,677). Our first
live research run burned 100,000 → 48,388 → 10,557 across a few
internal turns and then failed with *"The task, messages and tool
schemas exceed the remaining token budget."* A multi-turn tool workflow
cannot fit in the default. Workaround: the SDK's own env override
`OPENMINION_BRAIN_MAX_TOTAL_LLM_TOKENS=1000000` (set in
`demo/run-demo.sh`; the live probe below tests whether research now
completes). The default should scale with the workflow, or the packing
should cost far less.

### 17. The freshness verifier only accepts tool evidence from the agent's own turn (behaviour)
The SDK classifies each turn for freshness sensitivity with an LLM
classifier (`bootstrap/freshness_classify.py`) and then verifies the
answer (`modules/brain/runtime/verification/policy.py`,
`verify_freshness_answer`). For a turn classified time-sensitive, the
verifier requires (a) structured evidence — the turn's own
`action_result.outputs` non-empty — and (b) dated evidence — a key such
as `retrieved_at` / `published_at` / `date` somewhere in those outputs.
Text pasted into the prompt does **not** count: our digest subagent,
given the full article texts in its prompt, was refused with *"I
couldn't provide a grounded current news answer because Missing
live-data evidence for a freshness-sensitive answer.; Missing
exact-date evidence…"*. The fix is architectural, not a prompt tweak:
every phase that answers about news must call a tool itself, and the
tools must return structured dicts carrying dated keys. BriefMinion's
digest subagent and composer now fetch the sources themselves with
`fetch_article`, and `search_news` / `fetch_article` return dicts with
`retrieved_at` (and `published_at` when the feed provides it). This is
arguably the right guard — but it is undocumented, and the failure mode
(a polite refusal replacing the answer) looks like a model failure
until you read the SDK source.

### 18. Google News CBM article URLs are encrypted and unfetchable (data-source note)
Google News RSS `<link>` values are `news.google.com/rss/articles/CBM...`
URLs whose payload is encrypted/obfuscated (129 decoded bytes, no
protobuf structure, no printable strings — the known public CBM
decoders do not work on this format). Fetching one returns a ~608 KB
Google News SPA shell whose only text is "Google News". Article
fetching through Google News links is a dead end: the digest input in
our first live run was title-only. BriefMinion switched its primary
source to **Bing News RSS** (`bing.com/news/search?q=...&format=rss`),
whose links carry the real publisher URL in the `url=` query parameter;
Google News remains as a fallback for search only. Verified from this
machine: HackerNoon and SiliconANGLE articles fetch cleanly; Forbes
returns 403 (the workflow tolerates per-outlet failures).

### 19. A free-tier model in the tool loop does not stop on its own (behaviour)
In our first live probe (20 Nov 2026, Nemotron free via OpenRouter),
the research agent — instructed to search once and fetch at most 2
articles — searched 8+ times with new queries ("Bittensor Gensyn
Ritual io.net decentralized AI inference", …) and made 30 tool calls
across 23 model requests without ever concluding, burning the whole
remaining daily free-tier quota (19 requests) in ~4 minutes. The
model fetched 3 articles in its first parallel batch despite the
"at most 2" instruction, then kept expanding the research instead of
answering. Instruction wording alone does not converge this loop.
BriefMinion now enforces budgets deterministically in the tools
themselves: `search_news` allows exactly one search per run,
`fetch_article` refuses new URLs once `max_sources` articles are
fetched (or the attempt budget `max_sources + 4` is used up), retries
of a failed URL are refused, and re-fetches return cached text — every
refusal tells the model to stop and answer with what it has. A
generous `OPENMINION_BRAIN_MAX_TOOL_CALLS=30` env backstop bounds the
damage if the model ignores the refusals. Builders on a paced tier
should budget for the loop, not just the happy path: our full workflow
needs ~30 model requests when it converges, and a runaway turn can
burn a whole day's free quota in minutes.

## Mock end-to-end run (completed 20 Nov 2026)

The full workflow ran against a local scripted OpenAI-compatible server
(`tests/mock_provider.py`): research tools (real articles fetched from
live RSS, fetching until the source cap succeeds), subagent digest that
fetches the sources itself, structured-output compose after a source
verification fetch, approval-gated save, and a follow-up `ask` in the
same session — 0 fallbacks, brief saved with all sections, ≈31 model
requests. This proves the SDK wiring end to end; it does not prove
real-model behaviour (notably, the scripted model cannot exercise the
freshness classifier, so the live run is the real test of finding 17).

## Live-model runs

### Probe 1 — first live run (20 Nov 2026, failed; diagnosed)
Topic "decentralized AI inference", Nemotron free via OpenRouter.
Research hit the SDK's 100,000-token budget wall (finding 16); the
digest subagent was refused by the freshness verifier (finding 17);
article input was title-only because Google News CBM links are
unfetchable (finding 18). All three blockers were diagnosed from the
run's telemetry and the SDK source, and fixed in code (see findings).

### Probe 2 — research+digest probe (20 Nov 2026, failed; diagnosed)
Same topic, with the 1M token-budget override and the Bing + freshness
fixes. Research no longer hit the budget wall — but the agent looped
on tool calls instead (finding 19): 30 tool calls / 23 model requests
in ~4 minutes, never concluding, exhausting the day's remaining
OpenRouter free-tier quota (50 requests/day; 31 already used by probe
1 and the smoke test). The probe was stopped; the digest fix is still
unverified live. Fixed in code the same evening: deterministic
per-run tool budgets + tightened phase instructions + a research-turn
fallback that continues with already-fetched articles.

### Full live run + video run (21 Nov 2026, completed with fallbacks)
Topic "decentralized AI inference", Nemotron free via OpenRouter,
after the quota reset (research+digest probe OK earlier the same
morning, 222 s). Research + the digest subagent completed live
(3 articles fetched: HackerNoon 2026-11-05, SiliconAngle 2026-10-06,
CryptoBriefing 2026-11-03). The composer returned prose instead of
JSON, so the deterministic compose fallback built the brief (still a
validated `Brief` model). The agent-driven save ran with real human
approval ('y' at the prompt) and wrote the brief file at 00:27 UTC;
the save turn's completion call then hit free-models-per-day 429s
(retries 20 s / 45 s / 75 s, all failed) and the run fell through to
the direct-save prompt, where it blocked; the operator ended the run
at 00:37 UTC. The follow-up `ask` step never ran (no quota left).
The brief file itself is complete and genuine; the 1:55 demo video
was recorded from this run's terminal replay. No credits were bought.
Run record: `briefs/decentralized-ai-inference-2026-11-21.run.json`.

## Test evidence

- `python -m pytest tests/ -q` → 37 passed (35 unit + 2 mock
  end-to-end). No model key needed.
- Mock end-to-end: full brief workflow against a scripted local model
  (see above) — articles fetched until the cap, 0 fallbacks, brief +
  run log saved.
- Echo-provider smoke test: `briefminion brief ... --agent openminion`
  fails cleanly with exit code 1 and "No articles could be fetched..."
  (expected: echo cannot call tools).
- Live network checks (in the test suite): Bing News RSS returns items
  with direct publisher links; Google News RSS returns items; plain
  article fetch works.
