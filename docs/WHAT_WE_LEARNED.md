# What We Learned

Actionable product feedback from building BriefMinion on OpenMinion 0.1.22
for Cortensor Hackathon #5. Ordered by impact on the next builder.

> Status: draft from the build phase (20 Nov 2026); extended after the live
> model runs.

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

## 6. Document free-tier turn budgets
**Problem:** (to be confirmed in live runs) free-tier models cap tokens
per minute, while a default agent turn carries a large system prompt plus
tool schemas. Builders discover the limit by failing.
**Suggestion:** publish a rough per-turn token budget for the default
agent configuration, and a `doctor` check that estimates the size of the
next turn before it is sent.

## What worked well (keep doing this)
- The `@tool` decorator returning a plain callable makes tools unit-testable
  without a model — this shaped our whole test strategy.
- Provider switching by agent id (`--agent`) with no code change is real:
  the same program runs against echo, OpenRouter, or Portal by config.
- The SDK examples are copyable and accurate (apart from the `default`
  agent id in finding 2) — `tool_agent.py`, `sessions.py`,
  `structured_output.py`, and `delegation.py` were enough to build this
  project without reading runtime source.
