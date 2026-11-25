"""Drop pages whose frontmatter has ``draft: true``.

Usage::

    middleware:
      - mdbake.builtin.draft                      # module-level default
      - path: mdbake.builtin.draft:Draft          # or configurable
        options: {include_drafts: true}
"""

from __future__ import annotations

import logging

log = logging.getLogger("mdbake")


class Draft:
    def __init__(self, include_drafts: bool = False):
        self.include_drafts = include_drafts

    def on_page_source(self, page, *, site):
        if page.meta.get("draft") and not self.include_drafts:
            log.info("Draft page excluded: %s", page.src_path)
            page.skip = True
        return page


on_page_source = Draft().on_page_source
