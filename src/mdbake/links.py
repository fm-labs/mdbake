"""Rewrite relative links between docs (``.md`` -> page URL) and record anchors."""

from __future__ import annotations

import posixpath
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote, urlsplit

if TYPE_CHECKING:
    from markdown_it.rules_core import StateCore
    from markdown_it.token import Token

    from .files import File, Files


@dataclass
class LinkRef:
    """A link found in a page. ``target`` is None when it could not be resolved."""

    source: File
    url: str  # original URL as written
    target: File | None
    fragment: str | None
    broken: bool = False


def is_external(url: str) -> bool:
    """True for anything that is not a relative path (scheme, host, or site-absolute)."""
    parts = urlsplit(url)
    return bool(parts.scheme or parts.netloc or url.startswith("/"))


def relative_url(to_url: str, from_url: str) -> str:
    """Relative URL from page ``from_url`` to ``to_url`` (both site-root-relative)."""
    start = posixpath.dirname(from_url) or "."
    return posixpath.relpath(to_url, start)


def resolve_link(url: str, source: File, files: Files) -> tuple[str, LinkRef | None]:
    """Return ``(new_url, ref)``. External links are returned unchanged with ref None."""
    if is_external(url):
        return url, None
    parts = urlsplit(url)
    fragment = unquote(parts.fragment) or None
    path = unquote(parts.path)
    if not path:  # "#anchor" (same page) or "?query"
        return url, LinkRef(source, url, source, fragment)

    base = posixpath.dirname(source.src_path)
    target_path = posixpath.normpath(posixpath.join(base, path))
    if target_path == ".":
        target_path = ""
    if target_path == ".." or target_path.startswith("../"):
        return url, LinkRef(source, url, None, fragment, broken=True)

    target = files.get(target_path) if target_path else None
    if target is None:  # maybe a directory link -> its index page
        for index in ("index.md", "README.md", "index.markdown"):
            candidate = files.get(posixpath.join(target_path, index) if target_path else index)
            if candidate is not None and candidate.is_page:
                target = candidate
                break
    if target is None:
        return url, LinkRef(source, url, None, fragment, broken=True)

    new_url = quote(relative_url(target.url, source.url), safe="/")
    if parts.query:
        new_url += "?" + parts.query
    if parts.fragment:
        new_url += "#" + parts.fragment
    return new_url, LinkRef(source, url, target, fragment)


def _walk(tokens: list[Token]) -> Iterator[Token]:
    for tok in tokens:
        yield tok
        if tok.children:
            yield from _walk(tok.children)


def rewrite_links_rule(state: StateCore) -> None:
    """markdown-it core rule: rewrite ``href``/``src`` of link and image tokens."""
    page = state.env.get("page")
    files = state.env.get("files")
    if page is None or files is None:
        return
    refs: list[LinkRef] = state.env.setdefault("link_refs", [])
    for tok in _walk(state.tokens):
        if tok.type == "link_open":
            attr = "href"
        elif tok.type == "image":
            attr = "src"
        else:
            continue
        url = tok.attrGet(attr)
        if not isinstance(url, str):
            continue
        new_url, ref = resolve_link(url, page.file, files)
        if ref is not None:
            refs.append(ref)
        if new_url != url:
            tok.attrSet(attr, new_url)
