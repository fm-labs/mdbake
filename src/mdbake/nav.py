"""Site navigation: explicit (from config) or auto-discovered from the dir tree."""

from __future__ import annotations

import math
import posixpath
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Union

from .links import is_external
from .page import Page, pretty_title


@dataclass(eq=False)
class Section:
    name: str
    children: list[NavItem] = field(default_factory=list)
    page: Page | None = None  # optional index page the section title links to
    parent: Section | None = None
    explicit_title: str | None = None

    is_page = False
    is_section = True
    is_link = False

    @property
    def title(self) -> str:
        if self.explicit_title:
            return self.explicit_title
        if self.page is not None:
            return self.page.title
        return pretty_title(self.name)

    @property
    def ancestors(self) -> list[Section]:
        result, node = [], self.parent
        while node is not None:
            result.append(node)
            node = node.parent
        return result

    def __repr__(self) -> str:
        return f"Section({self.title!r}, children={len(self.children)})"


@dataclass(eq=False)
class Link:
    title: str
    url: str
    parent: Section | None = None

    is_page = False
    is_section = False
    is_link = True


NavItem = Union[Page, Section, Link]


@dataclass(eq=False)
class Navigation:
    items: list[NavItem]
    pages: list[Page]  # pages in nav order (for prev/next)

    def __iter__(self) -> Iterator[NavItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


Warn = Callable[[str], None]


def _noop_warn(msg: str) -> None:
    pass


def build_nav(config_nav: list | None, pages: list[Page], *, warn: Warn = _noop_warn) -> Navigation:
    """Build navigation, then wire ``previous_page``/``next_page``."""
    for page in pages:
        page.parent = None
        page.previous_page = page.next_page = None
    if config_nav:
        by_src = {p.src_path: p for p in pages}
        items = _parse_explicit(config_nav, by_src, None, warn, set())
    else:
        items = _auto_nav(pages)
    nav = Navigation(items=items, pages=list(_iter_pages(items)))
    link_pages(nav)
    return nav


def link_pages(nav: Navigation) -> None:
    for prev, nxt in zip(nav.pages, nav.pages[1:]):
        prev.next_page = nxt
        nxt.previous_page = prev


def _iter_pages(items: list[NavItem]) -> Iterator[Page]:
    seen: set[int] = set()

    def walk(items: list[NavItem]) -> Iterator[Page]:
        for item in items:
            if isinstance(item, Section):
                if item.page is not None and id(item.page) not in seen:
                    seen.add(id(item.page))
                    yield item.page
                yield from walk(item.children)
            elif isinstance(item, Page) and id(item) not in seen:
                seen.add(id(item))
                yield item

    return walk(items)


def _parse_explicit(
    raw: list, pages: dict[str, Page], parent: Section | None, warn: Warn, placed: set[int]
) -> list[NavItem]:
    items: list[NavItem] = []
    for entry in raw:
        title: Any
        if isinstance(entry, str):
            title, value = None, entry
        elif isinstance(entry, dict) and len(entry) == 1:
            title, value = next(iter(entry.items()))
        else:
            warn(f"nav: invalid entry {entry!r} (expected 'path', 'Title: path' or 'Title: [..]')")
            continue

        if isinstance(value, list):
            name = str(title) if title is not None else "Section"
            section = Section(name=name, parent=parent, explicit_title=name)
            section.children = _parse_explicit(value, pages, section, warn, placed)
            items.append(section)
        elif isinstance(value, str):
            if is_external(value):
                items.append(Link(title=str(title) if title is not None else value, url=value, parent=parent))
                continue
            page = pages.get(posixpath.normpath(value))
            if page is None:
                warn(f"nav: page '{value}' not found in docs_dir")
                continue
            if title is not None:
                page.nav_title = str(title)
            if id(page) not in placed:
                placed.add(id(page))
                page.parent = parent
            items.append(page)
        else:
            warn(f"nav: invalid value for {title!r}: {value!r}")
    return items


def _order(page: Page | None) -> float:
    if page is None:
        return math.inf
    value = page.meta.get("nav_order")
    try:
        return float(value) if value is not None else math.inf
    except (TypeError, ValueError):
        return math.inf


@dataclass
class _Dir:
    index: Page | None = None
    pages: list[Page] = field(default_factory=list)
    dirs: dict[str, _Dir] = field(default_factory=dict)


def _auto_nav(pages: list[Page]) -> list[NavItem]:
    root = _Dir()
    for page in pages:
        node = root
        for part in page.src_path.split("/")[:-1]:
            node = node.dirs.setdefault(part, _Dir())
        if page.is_index and node.index is None:
            node.index = page
        else:
            node.pages.append(page)

    def build(node: _Dir, parent: Section | None) -> list[NavItem]:
        entries: list[tuple[tuple, Any]] = []
        for page in node.pages:
            name = posixpath.basename(page.src_path).lower()
            entries.append(((_order(page), 0, name), page))
        for dirname, sub in node.dirs.items():
            entries.append(((_order(sub.index), 1, dirname.lower()), (dirname, sub)))
        entries.sort(key=lambda e: e[0])

        items: list[NavItem] = []
        for _, value in entries:
            if isinstance(value, Page):
                value.parent = parent
                items.append(value)
                continue
            dirname, sub = value
            section = Section(name=dirname, parent=parent, page=sub.index)
            section.children = build(sub, section)
            if not section.children and sub.index is not None:
                sub.index.parent = parent  # lone index page: no need for a section
                items.append(sub.index)
                continue
            if sub.index is not None:
                sub.index.parent = section
            items.append(section)
        return items

    items = build(root, None)
    if root.index is not None:
        root.index.parent = None
        items.insert(0, root.index)
    return items
