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
