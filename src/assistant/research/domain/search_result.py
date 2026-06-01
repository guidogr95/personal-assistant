from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """A single web search result.

    Immutable value object — equality is based on all three fields.
    """

    title: str
    url: str
    snippet: str
