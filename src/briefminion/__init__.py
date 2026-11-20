"""BriefMinion: a research-brief agent built on the OpenMinion 0.1 Python SDK.

Given a topic, BriefMinion searches live news (Google News RSS), fetches the
most relevant articles, distils them through a bounded subagent, composes a
structured brief, and saves it as Markdown — with human approval before the
file is written.
"""

__version__ = "0.1.0"
