"""BriefMinion workflow orchestration on top of the OpenMinion Python SDK.

One brief run has four phases, each a separate Agent sharing one session:

1. Research — the agent drives ``search_news`` + ``fetch_article`` itself.
2. Digest — a bounded subagent distils the fetched articles into facts.
3. Compose — the agent returns the brief as validated structured output.
4. Save — the agent calls the approval-gated ``save_brief`` tool.

Phases 2 and 4 have deterministic fallbacks (logged in the run record) so a
flaky free-tier model degrades the run instead of killing it.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from typing import Any, Callable

from openminion import (
    Agent,
    AgentOutputValidationError,
    ProviderError,
    TurnTimeoutError,
    subagent,
)

from .models import Brief, render_markdown, slugify
from .rss import fetch_url_text
from .tools import FetchedArticle, RunStore, create_tools

RESEARCH_INSTRUCTIONS = (
    "You are BriefMinion, a research assistant. Use search_news to find "
    "recent news about the user's topic, then fetch_article for the most "
    "relevant results (at most {max_sources}). Reply with one line per "
    "article you fetched: title and URL. Keep working until you have "
    "fetched articles or the tools report errors."
)

DIGEST_INSTRUCTIONS = (
    "You distil news articles into facts. Return at most 1200 characters: "
    "one short paragraph of key facts with dates, then one line per source "
    "in the form 'TITLE | DATE | one-fact summary'. Use only the articles "
    "given; do not invent facts."
)

COMPOSE_INSTRUCTIONS = (
    "You write research briefs. Return JSON only with fields: title, "
    "summary (2-3 sentences), key_points (up to 6 short bullets), timeline "
    "(up to 6 dated events with date and event), sources (title, url, "
    "published). Base every claim on the digest and sources given; never "
    "invent facts or URLs."
)

SAVE_INSTRUCTIONS = (
    "You save finished briefs. Call save_brief exactly once with the "
    "filename and markdown content given by the user."
)

ASK_INSTRUCTIONS = (
    "Answer questions about the research brief in this session. If the "
    "answer is not in the brief, say so plainly instead of guessing."
)

RATE_LIMIT_BACKOFF_SECONDS = (20, 45, 75)


def _is_rate_limit(error: ProviderError) -> bool:
    text = f"{error.code} {error.message}".lower()
    return "429" in text or "rate" in text or "quota" in text


def run_with_retry(
    agent: Agent, message: str, log: Callable[[str], None], **kwargs: Any
):
    """Run one agent turn, retrying rate limits with backoff."""
    attempts = list(RATE_LIMIT_BACKOFF_SECONDS) + [None]
    last_error: Exception | None = None
    for wait in attempts:
        try:
            return agent.run(message, **kwargs)
        except ProviderError as exc:
            last_error = exc
            if _is_rate_limit(exc) and wait is not None:
                log(f"rate limited ({exc.code}); waiting {wait}s before retry")
                time.sleep(wait)
                continue
            raise
        except TurnTimeoutError as exc:
            last_error = exc
            if wait is not None:
                log(f"turn timed out; retrying once after {wait}s")
                time.sleep(wait)
                continue
            raise
    assert last_error is not None  # for type checkers; loop always returns/raises
    raise last_error


def make_approval_callback(auto_approve: bool) -> Callable[[str, dict, str], bool]:
    """Build an approval callback: auto-approve with --yes, else ask on stdin."""

    def decide(tool_name: str, args: dict[str, Any], approval_id: str) -> bool:
        if auto_approve:
            print(f"approval: auto-approved {tool_name} ({approval_id})", file=sys.stderr)
            return True
        filename = args.get("filename", "?")
        answer = input(
            f"Approve {tool_name} writing '{filename}'? [y/N] "
        ).strip().lower()
        return answer in {"y", "yes"}

    return decide


def _fallback_fetch(store: RunStore, max_sources: int, log: Callable[[str], None]) -> None:
    """Deterministic fallback: fetch the top search results directly."""
    log("agent fetched 0 articles; falling back to direct fetch of top results")
    for item in store.search_results[:max_sources]:
        try:
            text = fetch_url_text(item.link, max_chars=2000)
        except Exception as exc:  # noqa: BLE001 - one bad URL must not kill the run
            log(f"fallback fetch failed for {item.link}: {exc}")
            continue
        if text:
            store.articles.append(
                FetchedArticle(url=item.link, title=item.title, text=text)
            )


def _digest_fallback(articles: list[FetchedArticle]) -> str:
    """Deterministic fallback digest: truncated article texts, joined."""
    parts = [f"{a.title}\n{a.text[:600]}" for a in articles]
    return "\n\n".join(parts)[:4000]


def run_brief(
    topic: str,
    agent_id: str | None = None,
    model: str | None = None,
    out_dir: str = "briefs",
    max_sources: int = 4,
    auto_approve: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the full brief workflow. Returns the run record."""
    log = log or (lambda message: print(message, file=sys.stderr))
    started = time.monotonic()
    slug = slugify(topic)
    session_id = f"briefminion-{slug}"
    day = date.today().isoformat()
    filename = f"{slug}-{day}.md"
    record: dict[str, Any] = {
        "topic": topic,
        "session_id": session_id,
        "agent_id": agent_id,
        "model": model,
        "fallbacks": [],
        "phases": {},
    }

    store = RunStore()
    search_news, fetch_article, save_brief = create_tools(store, out_dir)
    approval = make_approval_callback(auto_approve)

    # Phase 1 — research: the agent drives search + fetch.
    phase_started = time.monotonic()
    with Agent(
        agent_id=agent_id,
        model=model,
        instructions=RESEARCH_INSTRUCTIONS.format(max_sources=max_sources),
        tools=[search_news, fetch_article],
        forced_tools=["search_news"],
        session_id=session_id,
    ) as agent:
        research = run_with_retry(
            agent,
            f"Research this topic: {topic}",
            log,
            timeout_seconds=300,
        )
        log(f"research: {research.text.strip()[:300]}")

        if not store.articles and store.search_results:
            record["fallbacks"].append("fetch")
            _fallback_fetch(store, max_sources, log)
        if not store.articles:
            raise RuntimeError(
                "No articles could be fetched for this topic; "
                "search returned nothing usable."
            )

        # Phase 2 — digest: a bounded subagent distils the articles.
        digest_started = time.monotonic()
        digest = ""
        try:
            summarizer = subagent(
                agent,
                name="summarizer",
                instructions=DIGEST_INSTRUCTIONS,
                timeout_seconds=180,
            )
            digest_text = "\n\n".join(
                f"SOURCE: {a.title}\nURL: {a.url}\n{a.text}"
                for a in store.articles
            )
            digest = summarizer.run(
                f"Distil these articles:\n\n{digest_text[:6000]}"
            ).text
        except (ProviderError, TurnTimeoutError) as exc:
            record["fallbacks"].append("digest")
            log(f"subagent digest failed ({exc}); using fallback digest")
            digest = _digest_fallback(store.articles)
        record["phases"]["digest_seconds"] = round(time.monotonic() - digest_started, 1)
    record["phases"]["research_seconds"] = round(time.monotonic() - phase_started, 1)
    record["articles_fetched"] = len(store.articles)

    # Phase 3 — compose: validated structured output.
    compose_started = time.monotonic()
    source_lines = "\n".join(
        f"- {a.title} | {a.url}" for a in store.articles
    )
    with Agent(
        agent_id=agent_id,
        model=model,
        instructions=COMPOSE_INSTRUCTIONS,
        output_type=Brief,
        session_id=session_id,
    ) as composer:
        try:
            composed = run_with_retry(
                composer,
                f"Write the research brief for: {topic}\n\n"
                f"Digest:\n{digest}\n\nSources:\n{source_lines}",
                log,
                timeout_seconds=300,
            )
        except AgentOutputValidationError as exc:
            raise RuntimeError(
                f"Model did not return a valid brief JSON: {exc.raw_text[:500]}"
            ) from exc
    brief = composed.output
    record["phases"]["compose_seconds"] = round(time.monotonic() - compose_started, 1)

    markdown = render_markdown(brief, topic, generated_on=day)

    # Phase 4 — save: agent-driven, approval-gated.
    save_started = time.monotonic()
    saved = False
    with Agent(
        agent_id=agent_id,
        model=model,
        instructions=SAVE_INSTRUCTIONS,
        tools=[save_brief],
        forced_tools=["save_brief"],
        session_id=session_id,
    ) as saver:
        try:
            run_with_retry(
                saver,
                f"Save the brief with filename {filename} and this exact "
                f"markdown content:\n\n{markdown}",
                log,
                timeout_seconds=180,
                approval_callback=approval,
            )
            saved = store.saved_path is not None
        except (ProviderError, TurnTimeoutError) as exc:
            log(f"agent-driven save failed ({exc}); using direct save")
    if not saved:
        record["fallbacks"].append("save")
        if approval("save_brief", {"filename": filename}, "direct-save"):
            result = save_brief(filename, markdown)
            log(result)
            saved = store.saved_path is not None
    if not saved:
        raise RuntimeError("Brief was composed but not saved (approval denied).")
    record["phases"]["save_seconds"] = round(time.monotonic() - save_started, 1)

    record["saved_path"] = store.saved_path
    record["brief_title"] = brief.title
    record["total_seconds"] = round(time.monotonic() - started, 1)

    run_log_path = f"{out_dir}/{slug}-{day}.run.json"
    with open(run_log_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
    record["run_log_path"] = run_log_path
    return record


def run_ask(
    question: str,
    topic: str,
    agent_id: str | None = None,
    model: str | None = None,
    log: Callable[[str], None] | None = None,
) -> str:
    """Ask a follow-up question in the brief's session."""
    log = log or (lambda message: print(message, file=sys.stderr))
    session_id = f"briefminion-{slugify(topic)}"
    with Agent(
        agent_id=agent_id,
        model=model,
        instructions=ASK_INSTRUCTIONS,
        session_id=session_id,
    ) as agent:
        result = run_with_retry(agent, question, log, timeout_seconds=180)
    return result.text
