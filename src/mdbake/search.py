"""Build-time search index.

Each page's rendered HTML is split into sections at headings that carry an ``id``.
Every section becomes one index entry::

    {"t": section title, "p": page title, "u": "guide/install.html#requirements", "x": plain text}

URLs are relative to the site root. The index is written as a JavaScript file that
assigns ``window.mdbakeSearchIndex``, so the browser can load it with a ``<script>``
tag. That also works for sites opened straight from disk (``file://``), where
``fetch()`` / XHR of local files is blocked. The browser builds the actual search
index from these entries in a Web Worker (see ``theme/search.js``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from .page import Page

INDEX_GLOBAL = "mdbakeSearchIndex"

_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP = {"script", "style", "template", "noscript"}
# Tags that don't separate words; every other tag acts as whitespace.
_INLINE = {
    "a", "abbr", "b", "bdi", "bdo", "cite", "code", "del", "dfn", "em", "i", "ins", "kbd",
    "mark", "q", "s", "samp", "small", "span", "strong", "sub", "sup", "u", "var",
}
_WS_RE = re.compile(r"\s+")


def _squash(parts: list[str]) -> str:
    return _WS_RE.sub(" ", "".join(parts)).strip()


@dataclass
class Section:
    title: str
    anchor: str | None
    parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return _squash(self.parts)


class _SectionParser(HTMLParser):
    """Split HTML into sections at ``<hN id="...">`` headings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections = [Section("", None)]
        self._skip_depth = 0
        self._heading: str | None = None  # tag of the heading being read
        self._heading_parts: list[str] = []

    def _out(self) -> list[str]:
        return self._heading_parts if self._heading is not None else self.sections[-1].parts

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag in _HEADINGS and self._heading is None and dict(attrs).get("id"):
            self._heading = tag
            self._heading_parts = []
            self.sections.append(Section("", dict(attrs)["id"]))
        elif tag not in _INLINE:
            self._out().append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _INLINE:
            self._out().append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == self._heading:
            self.sections[-1].title = _squash(self._heading_parts)
            self._heading = None
        elif tag not in _INLINE:
            self._out().append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._out().append(data)


def split_sections(html: str) -> list[Section]:
    """Sections of ``html``; the first one holds the text before the first heading."""
    parser = _SectionParser()
    parser.feed(html)
    parser.close()
    return parser.sections


def is_searchable(page: Page) -> bool:
    """Pages opt out with ``search: false`` in their frontmatter."""
    return page.meta.get("search", True) is not False


def page_entries(page: Page) -> list[dict[str, str]]:
    page_title = page.title
    sections = split_sections(page.html)
    entries = []
    for i, section in enumerate(sections):
        if i == 0 and not section.text:
            continue  # nothing before the first heading
        url = page.url
        # The page's leading H1 links to the page itself, not to its anchor.
        if section.anchor and not (i == 1 and not sections[0].text and section.title == page.h1_title):
            url = f"{page.url}#{section.anchor}"
        entries.append({"t": section.title or page_title, "p": page_title, "u": quote(url, safe="/#"), "x": section.text})
    return entries


def build_index(pages: list[Page]) -> dict[str, Any]:
    docs: list[dict[str, str]] = []
    for page in pages:
        if is_searchable(page):
            docs.extend(page_entries(page))
    return {"docs": docs}


def index_script(index: dict[str, Any]) -> str:
    data = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    return f"window.{INDEX_GLOBAL}={data};\n"
