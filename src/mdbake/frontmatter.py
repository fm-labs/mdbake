"""Split YAML frontmatter from a Markdown document."""

from __future__ import annotations

import re
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?\r?\n)??(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.DOTALL
)


class FrontmatterError(ValueError):
    """Raised when frontmatter exists but is not a valid YAML mapping."""


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(meta, body)``. Documents without frontmatter yield ``({}, text)``."""
    text = text.lstrip("﻿")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group("yaml") or ""
    try:
        meta = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML frontmatter: {exc}") from exc
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return meta, text[match.end():]
