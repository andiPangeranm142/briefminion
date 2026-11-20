#!/usr/bin/env bash
# One-command demo run for the BriefMinion video.
# Requires a configured model provider (see README):
#   openminion setup --provider cortensor-portal --model oss-20b --no-chat
# or an OpenRouter free model. Expects .venv to exist.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

# The provider key lives in .env (OPENROUTER_API_KEY); the SDK reads it
# from the environment via api_key_env. Load it if present.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# httpx (used by OpenMinion) cannot parse bracketed IPv6 entries in
# NO_PROXY; simplify it so provider calls work in this sandbox.
export NO_PROXY=localhost,127.0.0.1
export no_proxy=localhost,127.0.0.1

# The SDK's default per-conversation token budget is 100,000, and its own
# per-request context packing burns ~12k estimated tokens per trivial turn,
# so a multi-turn tool workflow exhausts it mid-research. Raise it via the
# SDK's own env override (see docs/BUILDING_BLOCKS.md finding 16).
export OPENMINION_BRAIN_MAX_TOTAL_LLM_TOKENS=1000000

# Backstop against a runaway tool loop: each phase needs at most ~8 tool
# calls (1 search + up to 7 fetches in research), so 30 per phase can only
# trip on a pathological loop. The tools' own per-run budgets (one search,
# capped fetches) are the real convergence mechanism; this just bounds
# the damage if the model ignores their refusals.
export OPENMINION_BRAIN_MAX_TOOL_CALLS=30

TOPIC="decentralized AI inference"

echo "=== BriefMinion demo: researching '$TOPIC' ==="
# The save step prompts for human approval by default (that approval gate
# is part of the demo). Set DEMO_AUTO_APPROVE=1 for a non-interactive run.
if [ "${DEMO_AUTO_APPROVE:-0}" = "1" ]; then
  briefminion brief "$TOPIC" --max-sources 3 --yes
else
  briefminion brief "$TOPIC" --max-sources 3
fi

BRIEF_FILE=$(ls -t briefs/decentralized-ai-inference-*.md | head -1)
echo ""
echo "=== Saved brief: $BRIEF_FILE ==="
cat "$BRIEF_FILE"

echo ""
echo "=== Follow-up in the same session ==="
briefminion ask "What is the single most important point in this brief?" \
  --topic "$TOPIC"
