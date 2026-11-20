#!/usr/bin/env bash
# One-command demo run for the BriefMinion video.
# Requires a configured model provider (see README):
#   openminion setup --provider cortensor-portal --model oss-20b --no-chat
# or an OpenRouter free model. Expects .venv to exist.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

# httpx (used by OpenMinion) cannot parse bracketed IPv6 entries in
# NO_PROXY; simplify it so provider calls work in this sandbox.
export NO_PROXY=localhost,127.0.0.1
export no_proxy=localhost,127.0.0.1

# The SDK's default per-conversation token budget is 100,000, and its own
# per-request context packing burns ~12k estimated tokens per trivial turn,
# so a multi-turn tool workflow exhausts it mid-research. Raise it via the
# SDK's own env override (see docs/BUILDING_BLOCKS.md finding 16).
export OPENMINION_BRAIN_MAX_TOTAL_LLM_TOKENS=1000000

TOPIC="decentralized AI inference"

echo "=== BriefMinion demo: researching '$TOPIC' ==="
briefminion brief "$TOPIC" --max-sources 3 --yes

BRIEF_FILE=$(ls -t briefs/decentralized-ai-inference-*.md | head -1)
echo ""
echo "=== Saved brief: $BRIEF_FILE ==="
cat "$BRIEF_FILE"

echo ""
echo "=== Follow-up in the same session ==="
briefminion ask "What is the single most important point in this brief?" \
  --topic "$TOPIC"
