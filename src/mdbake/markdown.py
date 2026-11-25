"""markdown-it factory: GFM preset, plugins, heading ids, code highlighting."""

from __future__ import annotations

import html
import re
import unicodedata

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.token import Token
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from .links import rewrite_links_rule

try:  # Pygments is optional
    import pygments
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    _FORMATTER = HtmlFormatter(nowrap=True)
except ImportError:  # pragma: no cover
    pygments = None


def slugify(text: str) -> str:
    """GitHub-style slug: lowercase, drop punctuation, spaces become dashes."""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    text = text.replace(" ", "-")
    return text or "section"


def unique_id(candidate: str, used: set[str]) -> str:
    result, n = candidate, 0
    while result in used:
        n += 1
        result = f"{candidate}-{n}"
    used.add(result)
    return result


def inline_text(token: Token) -> str:
    """Plain text of an inline token (formatting and raw HTML stripped)."""
    if not token.children:
        return token.content.strip()
    parts = []
    for child in token.children:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif child.type == "image":
            parts.append(child.content)
    return "".join(parts).strip()


def heading_ids_rule(state: StateCore) -> None:
    """Give every heading a unique ``id`` and record ``(level, title, id)`` in env."""
    used: set[str] = state.env.setdefault("heading_ids", set())
    headings: list = state.env.setdefault("headings", [])
    tokens = state.tokens
    for i, tok in enumerate(tokens):
        if tok.type != "heading_open":
            continue
        title = inline_text(tokens[i + 1]) if i + 1 < len(tokens) else ""
        anchor = unique_id(str(tok.attrGet("id") or slugify(title)), used)
        tok.attrSet("id", anchor)
        headings.append((int(tok.tag[1]), title, anchor))


def highlight_code(code: str, lang: str, attrs: str) -> str:
    if pygments is None or not lang:
        return ""
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        return ""
    body = pygments.highlight(code, lexer, _FORMATTER)
    lang_attr = html.escape(lang, quote=True)
    return f'<pre class="highlight"><code class="language-{lang_attr}">{body}</code></pre>'


def pygments_css(light: str = "default", dark: str | None = "monokai") -> str:
    if pygments is None:  # pragma: no cover
        return ""
    css = HtmlFormatter(style=light).get_style_defs(".highlight")
    if dark:
        dark_css = HtmlFormatter(style=dark).get_style_defs(".highlight")
        css += "\n@media (prefers-color-scheme: dark) {\n" + dark_css + "\n}\n"
    return css


def create_markdown(*, highlight: bool = True) -> MarkdownIt:
    """Create a GFM-like renderer with heading ids and relative link rewriting.

    Per-render ``env`` keys used: ``page`` + ``files`` (enable link rewriting);
    the render fills ``headings`` and ``link_refs``.
    """
    md = MarkdownIt(
        "gfm-like",
        {"html": True, "linkify": True, "typographer": False,
         "highlight": highlight_code if highlight else None},
    )
    md.use(tasklists_plugin).use(footnote_plugin).use(deflist_plugin)
    md.core.ruler.push("mdbake_heading_ids", heading_ids_rule)
    md.core.ruler.push("mdbake_links", rewrite_links_rule)
    return md
