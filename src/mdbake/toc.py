"""Table of contents built from page headings."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class AnchorLink:
    title: str
    id: str
    level: int
    children: list[AnchorLink] = field(default_factory=list)

    @property
    def url(self) -> str:
        return "#" + self.id


def build_toc(headings: Iterable[tuple[int, str, str]], max_level: int = 6) -> list[AnchorLink]:
    """Nest ``(level, title, id)`` tuples into a tree of :class:`AnchorLink`."""
    root: list[AnchorLink] = []
    stack: list[AnchorLink] = []
    for level, title, anchor in headings:
        if level > max_level:
            continue
        link = AnchorLink(title=title, id=anchor, level=level)
        while stack and stack[-1].level >= level:
            stack.pop()
        (stack[-1].children if stack else root).append(link)
        stack.append(link)
    return root
