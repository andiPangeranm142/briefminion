# BriefMinion — demo video narration script

Target length: ~2:30 (limit 1–5 minutes). Male voiceover, English.
Footage: real terminal recording of `demo/run-demo.sh` — no slides.

---

## Narration

[0:00] "This is BriefMinion — a research-brief agent built on the OpenMinion
Python SDK for Cortensor Hackathon 5. One command, one topic, one brief."

[0:12] "I run: briefminion brief, decentralized AI inference. The agent
searches live news itself — it picks the sources, not a script."

[0:28] "It fetches the three most relevant articles, then a bounded subagent
distils them into dated facts."

[0:42] "Then the agent composes the brief as validated structured output —
title, summary, key points, timeline, sources — and every claim traces back
to a fetched article."

[0:58] "Before anything is written to disk, the save step asks for human
approval. This is a real approval gate on a dangerous tool, not a formality."

[1:12] "And here is the result: a dated Markdown brief, saved with a run
record of timings, sources, and fallbacks used."

[1:26] "Because the whole run shares one session, I can ask follow-up
questions without re-searching."

[1:38] "What is the single most important point in this brief? The agent
answers from the brief's own context."

[1:52] "BriefMinion runs on any OpenMinion provider. The intended route is
Cortensor Portal — hosted decentralized inference — and the same code runs
on a free OpenRouter model for development."

[2:08] "The code, the tests, and the full building-blocks report are on
GitHub. A simple agent that works reliably — that was the goal."

---

## Shot list (terminal recording)

1. `cat demo/run-demo.sh` — show the one command (5s).
2. Run `./demo/run-demo.sh` — research phase, tool calls visible (60s,
   speed up idle waits in edit if needed; never fake the output).
3. `cat` the saved brief — scroll through summary, key points, sources (25s).
4. Follow-up `ask` run (20s).
5. `python -m pytest tests/ -q` — 24 passed (10s).
6. End card: repo URL + hackathon name (5s).

## Recording notes
- Terminal: 1280x720 capture, font large enough to read at 720p.
- Do NOT show any API key on screen; keys come from the environment.
- If the live run hits a free-tier rate limit, the retry backoff is part of
  the honest footage — keep it, or re-record once; do not edit it to look
  instant.
