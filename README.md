# BriefMinion

A research-brief agent built on the **OpenMinion 0.1 Python SDK** for
**Cortensor Hackathon #5** (Cortensor Mainnet Full Alpha).

Give it a topic; it searches live news, fetches the most relevant articles,
distils them through a bounded subagent, composes a structured brief, and
saves it as Markdown — with human approval before the file is written.

```bash
briefminion brief "Cortensor Mainnet Full Alpha"
# → briefs/cortensor-mainnet-full-alpha-2026-11-20.md

briefminion ask "What did the brief say about Portal?" --topic "Cortensor Mainnet Full Alpha"
```

## Why this project

The hackathon asks for one useful, repeatable workflow on the OpenMinion
SDK. A research brief is exactly that: the same command, any topic, a
verifiable artefact at the end. The agent — not a script — decides which
sources matter, and every claim in the brief traces back to a fetched
article with a link.

## How it works

One brief run has four phases, each a separate `Agent` sharing one session
(`briefminion-<topic-slug>`):

| Phase | What happens | OpenMinion building blocks |
| --- | --- | --- |
| 1. Research | The agent drives `search_news` (Bing News RSS, keyless; Google News fallback) and `fetch_article` itself, picking the most relevant sources | `@tool` (read-only, idempotent), `forced_tools`, sessions |
| 2. Digest | A bounded subagent fetches the sources itself and distils them into dated facts | `subagent()`, timeouts |
| 3. Compose | The agent verifies the sources, then returns the brief as Pydantic-validated JSON | `output_type`, `AgentOutputValidationError`, `forced_tools` |
| 4. Save | The agent calls the approval-gated `save_brief` tool | `dangerous=True` tool, `approval_callback` |

Follow-up questions (`briefminion ask ...`) run in the same session, so the
agent answers from the brief's context instead of re-searching.

Why the digest subagent and the composer fetch articles themselves instead
of working from pasted text: the SDK's freshness verifier only accepts
tool-output evidence produced in the agent's own turn (see
[docs/BUILDING_BLOCKS.md](docs/BUILDING_BLOCKS.md) finding 17) — a turn
that only saw pasted text is refused. Each phase reads the sources it
cites, and the tools return structured results carrying `retrieved_at` /
`published_at` as dated evidence.

Free-tier reality: model calls are paced (short prompts, truncated article
text, at most 4 sources) and rate-limit errors are retried with backoff
(20s / 45s / 75s). If the subagent digest, the compose step, or the
agent-driven save fails, a deterministic fallback completes the run — and
the run record says so (see `briefs/<topic>-<date>.run.json`).

> Token budget: the SDK's default per-conversation budget (100,000) is
> exhausted mid-research by its own context packing. Live runs need the
> SDK's env override `OPENMINION_BRAIN_MAX_TOTAL_LLM_TOKENS=1000000`
> (already set in `demo/run-demo.sh`; see BUILDING_BLOCKS.md finding 16).
> The tools also enforce per-run budgets (one search, capped fetches)
> because a free-tier model in the tool loop does not reliably stop on
> its own (finding 19).

## Setup

Requires Python 3.11+.

```bash
git clone https://github.com/andiPangeranm142/briefminion.git
cd briefminion
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

### Model provider

BriefMinion runs on any configured OpenMinion provider. Two free paths:

**1. Cortensor Portal (the intended route)** — hosted Cortensor inference:

```bash
export CORTENSOR_API_KEY=<your-portal-key>
openminion setup --provider cortensor-portal --model oss-20b --no-chat
briefminion brief "your topic"
```

Portal access is coordinated with the hackathon team via the Cortensor
Discord (linked from the hackathon page).

**2. OpenRouter free tier (development / fallback)** — any `:free` model
with tool support, e.g. `nvidia/nemotron-3-ultra-550b-a55b:free`:

```bash
export OPENROUTER_API_KEY=<your-key>
openminion setup --provider openrouter \
  --model nvidia/nemotron-3-ultra-550b-a55b:free --no-chat
briefminion brief "your topic"
```

Or pick a configured agent / model per run:

```bash
briefminion brief "your topic" --agent openminion --model <model-id>
```

## Run

```bash
# Research a topic (prompts for approval before saving)
briefminion brief "quantum computing"

# Auto-approve the save step (scripted / demo runs)
briefminion brief "quantum computing" --yes

# Fewer sources, custom output dir
briefminion brief "quantum computing" --max-sources 3 --out-dir ./out

# Follow-up in the same session
briefminion ask "Which source is the most recent?" --topic "quantum computing"
```

Output: `briefs/<topic-slug>-<date>.md` plus a run record
`briefs/<topic-slug>-<date>.run.json` (phase timings, sources fetched,
fallbacks used, session id).

## Tests

```bash
python -m pytest tests/ -q
```

37 tests, no model key needed: RSS parsing (Bing + Google), HTML
stripping, brief rendering, tool behaviour (including the save guard
and the per-run tool budgets), retry/approval helpers, HTTP 429 retry
— plus live checks that the keyless Bing News RSS endpoint (direct
publisher links) and Google News RSS endpoint work from the machine,
and a full end-to-end run of the brief workflow against a scripted
local mock model (`tests/mock_provider.py`).

> Sandbox note: OpenMinion builds its HTTP client with
> `httpx.Client(trust_env=True)`, and httpx 0.28.1 cannot parse bracketed
> IPv6 entries in `NO_PROXY` (e.g. `[::1]`), failing every provider call
> before any request is sent. If you hit
> `InvalidURL: Invalid port: ':1]'`, run with a simplified
> `NO_PROXY=localhost,127.0.0.1` (see `demo/run-demo.sh`).

## Project layout

```
src/briefminion/
  __main__.py   CLI (brief / ask)
  agent.py      workflow orchestration, retry, approval
  tools.py      @tool definitions (search_news, fetch_article, save_brief)
  rss.py        Bing News RSS (primary) + Google News RSS (fallback) + article fetching (no API key)
  models.py     Brief schema (Pydantic) + Markdown rendering
tests/          pytest suite (37 tests)
docs/
  BUILDING_BLOCKS.md   OpenMinion blocks tested: what worked, what did not
  WHAT_WE_LEARNED.md   actionable product feedback from building this
demo/
  run-demo.sh   one-command demo run used in the video
  script.md     demo video narration script
```

## Hackathon submission

- **Demo video:** https://www.youtube.com/watch?v=nSxZCcTDRuU (1:55, filmed live 21 Nov 2026)
- **DoraHacks Build:** https://dorahacks.io/build/51475 (submitted 21 Nov 2026)
- **Building blocks tested:** [docs/BUILDING_BLOCKS.md](docs/BUILDING_BLOCKS.md)
- **What we learned:** [docs/WHAT_WE_LEARNED.md](docs/WHAT_WE_LEARNED.md)
- **License:** MIT

Built for Cortensor Hackathon #5 on DoraHacks
(https://dorahacks.io/hackathon/2418/detail). OpenMinion is the
[openminion/openminion](https://github.com/OpenMinion/openminion) runtime
(0.1.22); no affiliation beyond using the SDK.
