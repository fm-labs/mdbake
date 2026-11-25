"""The :class:`Page` model."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .files import File
from .toc import AnchorLink

if TYPE_CHECKING:
    from .nav import Section


def pretty_title(name: str) -> str:
    """``getting-started`` -> ``Getting started``."""
    text = name.replace("-", " ").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else name


@dataclass(eq=False)
class Page:
    file: File
    meta: dict[str, Any] = field(default_factory=dict)
    markdown: str = ""
    html: str = ""
    toc: list[AnchorLink] = field(default_factory=list)
    h1_title: str | None = None
    nav_title: str | None = None
    skip: bool = False
    anchors: set[str] = field(default_factory=set)
    parent: Section | None = None
    previous_page: Page | None = None
    next_page: Page | None = None

    is_page = True
    is_section = False
    is_link = False

    @property
    def src_path(self) -> str:
        return self.file.src_path

    @property
    def url(self) -> str:
        return self.file.url

    @property
    def is_index(self) -> bool:
        return self.file.is_index

    @property
    def is_homepage(self) -> bool:
        return self.url == "index.html"

    @property
    def title(self) -> str:
        """Explicit nav title > frontmatter ``title`` > first H1 > file name."""
        meta_title = self.meta.get("title")
        return self.nav_title or (str(meta_title) if meta_title else None) or self.h1_title or self._fallback_title()

    def _fallback_title(self) -> str:
        directory, name = posixpath.split(self.src_path)
        if self.is_index:
            return pretty_title(posixpath.basename(directory)) if directory else "Home"
        return pretty_title(name.rsplit(".", 1)[0])

    @property
    def ancestors(self) -> list[Section]:
        result = []
        node = self.parent
        while node is not None:
            result.append(node)
            node = node.parent
        return result

    def __repr__(self) -> str:
        return f"Page({self.src_path!r})"
