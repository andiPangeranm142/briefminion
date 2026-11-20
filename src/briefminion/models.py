"""Structured brief model and Markdown rendering."""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    title: str
    url: str
    published: str = ""


class TimelineEvent(BaseModel):
    date: str
    event: str


class Brief(BaseModel):
    """The structured research brief the agent must return as JSON."""

    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list, max_length=6)
    timeline: list[TimelineEvent] = Field(default_factory=list, max_length=6)
    sources: list[SourceItem] = Field(default_factory=list, max_length=8)


def slugify(topic: str) -> str:
    """Turn a topic into a safe filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug or "brief"


def render_markdown(brief: Brief, topic: str, generated_on: str | None = None) -> str:
    """Render a Brief as a dated Markdown document."""
    day = generated_on or date.today().isoformat()
    lines = [
        f"# {brief.title}",
        "",
        f"_Research brief on **{topic}** — generated {day} by BriefMinion "
        "(OpenMinion 0.1 Python SDK)._",
        "",
        "## Summary",
        "",
        brief.summary,
        "",
    ]
    if brief.key_points:
        lines += ["## Key points", ""]
        lines += [f"- {point}" for point in brief.key_points]
        lines += [""]
    if brief.timeline:
        lines += ["## Timeline", ""]
        lines += [f"- **{event.date}** — {event.event}" for event in brief.timeline]
        lines += [""]
    if brief.sources:
        lines += ["## Sources", ""]
        for source in brief.sources:
            stamp = f" ({source.published})" if source.published else ""
            lines.append(f"- [{source.title}]({source.url}){stamp}")
        lines += [""]
    return "\n".join(lines)
