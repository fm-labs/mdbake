"""Inject default frontmatter values and validate required keys.

Usage::

    middleware:
      - path: mdbake.builtin.frontmatter_defaults:FrontmatterDefaults
        options:
          defaults: {author: Docs Team}
          required: [title]
          strict: false        # true: raise instead of warn
"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any


class FrontmatterDefaults:
    def __init__(self, defaults: dict[str, Any] | None = None,
                 required: Iterable[str] = (), strict: bool = False):
        self.defaults = dict(defaults or {})
        self.required = list(required)
        self.strict = strict

    def on_page_source(self, page, *, site):
        if page.skip:
            return page
        for key, value in self.defaults.items():
            page.meta.setdefault(key, copy.deepcopy(value))
        missing = [key for key in self.required if key not in page.meta]
        if missing:
            message = f"{page.src_path}: missing required frontmatter: {', '.join(missing)}"
            if self.strict:
                raise ValueError(message)
            site.warn(message)
        return page
