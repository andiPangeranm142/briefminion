# What We Learned

Actionable product feedback from building BriefMinion on OpenMinion 0.1.22
for Cortensor Hackathon #5. Ordered by impact on the next builder.

> Status: extended 20 Nov 2026 after the first live-model runs
> (OpenRouter free tier) and the mock end-to-end run.

## 1. Make the echo provider honest about tools
**Problem:** the credential-free bring-up path silently ignores
`forced_tools` — a builder's first tool example looks like it "works"
(it exits 0) while no tool ever ran.
**Suggestion:** print a warning when a run requests tools under the echo
provider ("echo provider cannot execute tools; configure a model provider
to test tool calls"), or fail fast with that message.

## 2. One default agent id, everywhere
**Problem:** `config init` creates agent `openminion`, but the docs and
the `provider_switching.py` example reference `--agent default`.
**Suggestion:** standardise on one id (either is fine) and update the
docs, examples, and `setup` output to match.

## 3. Let `setup` write config without a credential
**Problem:** `setup --provider ...` fails without the env var, so a
builder cannot prepare a project before their key arrives, and CI cannot
pre-configure providers.
**Suggestion:** write the config with a clear warning that the credential
is missing, and let `doctor --check-turn` remain the live check.

## 4. Publish the Hackathon #5 submission repo URL in the docs
**Problem:** weeks after kickoff, the docs still say the submission
repository URL "will be added before kickoff", and no public repo exists
under the `cortensor` or `OpenMinion` orgs. Builders cannot verify where
their PR should go.
**Suggestion:** update the docs page with the repo URL and the exact
submission deadline with its timezone, and pin the same in Discord.

## 5. Resolve the Portal tool-calling contradiction
**Problem:** the 0.1.22 CLI advertises native tool calls on
`cortensor-portal`, while the Cortensor docs say tool calling "is not
exposed on the hosted compatibility routes". Builders cannot plan around
both statements.
**Suggestion:** update whichever is stale, and add a dated note to the
Portal docs page when tool support changes.

## 6. Fix (or honestly document) the `auto_fact_extraction` flag
**Problem:** the top-level `"brain": {"auto_fact_extraction":
{"enabled": false}}` setting is parsed into `module_configs.brain` but
does not stop the `submit_output` memory extractor. In our current mock
brief run, 16 of 31 model requests were `submit_output` turns — 8
freshness-classifier calls, 4 task-revision turns, and 4 memory
extractor turns that the flag should have gated. Each one costs a model
round trip on a paced free tier.
**Suggestion:** make the flag actually gate extraction, or remove it
from guidance and document the extractor's cost so builders can budget
for it.

## 7. Don't require `default_agent` when the caller names the agent
**Problem:** a multi-agent config fails at construction time unless
`default_agent` is set, even for `Agent(agent_id="...")`.
**Suggestion:** resolve the default lazily — only when no explicit agent
id is given.

## 8. Document the tool-result envelope
**Problem:** tool results reach the model wrapped in
`{"status", "summary", "outputs": {"data"}}`. Builders writing local
test harnesses (or parsing history) must discover the shape by
inspection.
**Suggestion:** one paragraph in the Python SDK docs showing the envelope
and noting the token overhead per tool round trip.

## 9. Sanitize proxy env for the httpx client
**Problem:** `httpx.Client(trust_env=True)` fails to construct when
`NO_PROXY` contains bracketed IPv6 entries (`[::1]`), which some
sandboxes set by default — every provider call then fails before any
request is sent.
**Suggestion:** strip bracketed entries, or build the client with
`trust_env=False` and explicit proxy support.

## 10. Raise (or scale) the default per-conversation token budget
**Problem:** the default budget is 100,000 tokens per conversation, and
the SDK's own per-request context packing burns ~12k estimated tokens
for a trivial turn — our first live research run exhausted the budget
mid-task (*"The task, messages and tool schemas exceed the remaining
token budget"*). A multi-turn tool workflow cannot fit in the default,
and the failure looks like a model error.
**Suggestion:** raise the default for tool-using agents, or scale it
with the number of tools/turns; at minimum, surface the remaining
budget in the turn error so builders find the
`OPENMINION_BRAIN_MAX_TOTAL_LLM_TOKENS` override without reading SDK
source.

## 11. Document the freshness guard — and make its failure diagnosable
**Problem:** a turn the freshness classifier marks time-sensitive is
refused unless the agent's own turn produced dated tool evidence — text
pasted into the prompt does not count. Our digest subagent, given full
article texts, was replaced by a polite refusal that looked exactly
like a model failure; only reading
`modules/brain/runtime/verification/policy.py` explained it. The guard
itself is reasonable (it forces agents to ground news answers in live
tool output), but it is undocumented.
**Suggestion:** document the contract (what counts as evidence, which
keys are dated, how to satisfy it from a subagent), and include the
verifier's reason codes in the turn log instead of only in the reply
text.

## 12. Give the tool loop a convergence signal (or a cheap per-turn cap)
**Problem:** nothing in the default loop tells an agent "you have
enough". Our research agent, told to fetch at most 2 articles, searched
8+ times and made 30 tool calls without concluding — burning a whole
day's free-tier quota in ~4 minutes. The only SDK-side guard is the
per-conversation `OPENMINION_BRAIN_MAX_TOOL_CALLS` budget, which fails
the turn when tripped instead of letting the agent conclude with what
it has.
**Suggestion:** add a per-turn tool-call budget that, when reached,
injects a "budget used — answer with what you have" message into the
turn instead of erroring, and surface the remaining tool budget in the
turn log so builders can see a runaway loop forming.

## What worked well (keep doing this)
- The `@tool` decorator returning a plain callable makes tools unit-testable
  without a model — this shaped our whole test strategy.
- Provider switching by agent id (`--agent`) with no code change is real:
  the same program runs against echo, OpenRouter, or Portal by config.
- The provider abstraction made a local mock model possible: pointing the
  `openai` slot at a scripted localhost server exercised the entire
  workflow (tools, subagent, structured output, approval, sessions)
  without any API key. That is a genuinely good property for a hackathon
  SDK.
- The SDK examples are copyable and accurate (apart from the `default`
  agent id in finding 2) — `tool_agent.py`, `sessions.py`,
  `structured_output.py`, and `delegation.py` were enough to build this
  project without reading runtime source.
