"""Tests for the structured brief model and Markdown rendering."""

import pytest
from pydantic import ValidationError

from briefminion.models import Brief, SourceItem, TimelineEvent, render_markdown, slugify


def test_slugify():
    assert slugify("Cortensor Mainnet Full Alpha!") == "cortensor-mainnet-full-alpha"
    assert slugify("  spaces  & stuff ") == "spaces-stuff"
    assert slugify("!!!") == "brief"


def test_brief_rejects_too_many_key_points():
    with pytest.raises(ValidationError):
        Brief(
            title="t",
            summary="s",
            key_points=["p"] * 7,
        )


def test_render_markdown_contains_all_sections():
    brief = Brief(
        title="Quantum Brief",
        summary="Things happened.",
        key_points=["First point", "Second point"],
        timeline=[TimelineEvent(date="2026-11-20", event="Launch day")],
        sources=[
            SourceItem(
                title="Story",
                url="https://example.com/story",
                published="2026-11-20",
            )
        ],
    )
    markdown = render_markdown(brief, "quantum", generated_on="2026-11-20")
    assert markdown.startswith("# Quantum Brief")
    assert "generated 2026-11-20 by BriefMinion" in markdown
    assert "- First point" in markdown
    assert "**2026-11-20** — Launch day" in markdown
    assert "[Story](https://example.com/story) (2026-11-20)" in markdown


def test_render_markdown_skips_empty_sections():
    brief = Brief(title="Empty", summary="Nothing yet.")
    markdown = render_markdown(brief, "nothing")
    assert "## Key points" not in markdown
    assert "## Timeline" not in markdown
    assert "## Sources" not in markdown
