# mdbake

A minimal Markdown → HTML documentation site generator.

- Reads all `*.md` files recursively from a docs directory
- Renders GitHub-flavored Markdown: tables, task lists, strikethrough, autolinks, footnotes, definition lists, Pygments code highlighting
- Builds navigation from `mdbake.yml`, or automatically from the directory tree
- Rewrites links between `.md` files into relative `.html` links and warns about broken links and missing `#anchors`
- Generates an in-page table of contents from headings
- Full-text search: a section-level index built at build time, searched in the browser in a Web Worker
- Extensible through a middleware chain (frontmatter processing, text substitution, HTML post-processing, ...)

All output links are relative, so the generated site works when opened straight from disk (`file://`).

## Installation

Requires Python 3.10+.

```bash
pip install -e .            # or: uv pip install -e .
pip install -e '.[dev]'     # with pytest
```

## Usage

```bash
mdbake build                          # uses ./mdbake.yml if present, else docs/ -> site/
mdbake build -f path/to/mdbake.yml    # explicit config file
mdbake build -d docs -o site          # override docs_dir / site_dir
mdbake build --clean --strict         # wipe site_dir first; fail on warnings
```

| Option | Meaning |
|---|---|
| `-f, --config` | Config file (default: `./mdbake.yml` if it exists) |
| `-d, --docs-dir` | Markdown source directory (overrides config) |
| `-o, --site-dir` | Output directory (overrides config) |
| `--clean` | Delete `site_dir` before building (refuses if it contains `docs_dir`) |
| `-s, --strict` | Exit with an error if there were any warnings |
| `-v, --verbose` / `-q, --quiet` | More / less output |

## Configuration

`mdbake.yml` (paths are relative to the config file):

```yaml
site_name: My Docs
docs_dir: docs
site_dir: site
templates_dir: null            # optional theme override
toc_depth: 3                   # deepest heading level in "On this page"
search: true                   # build the search index and show the search box
nav:                           # optional; auto-generated from the dir tree if omitted
  - Home: index.md
  - Guide:
      - guide/install.md       # title taken from the page
      - Usage: guide/usage.md  # explicit title
  - GitHub: https://github.com/example/project
middleware:
  - mdbake.builtin.draft
  - path: mdbake.builtin.frontmatter_defaults:FrontmatterDefaults
    options: {defaults: {author: Docs Team}, required: [title]}
extra:                         # free-form, available in templates
  lang: en
```

### Pages and URLs

| Source | Output |
|---|---|
| `foo/bar.md` | `foo/bar.html` |
| `foo/index.md` or `foo/README.md` | `foo/index.html` |
| other files (images, ...) | copied as-is |

Dotfiles and dot-directories are ignored. Optional YAML frontmatter at the top of a page is available as `page.meta`.

**Page title**: explicit nav title → frontmatter `title` → first `# H1` → file name.

### Navigation

Without `nav`, the directory tree is used: the root `index.md` first, then pages, then
sub-directories as sections (a directory's `index.md` becomes the section link). Add
`nav_order: <number>` to a page's frontmatter to reorder. Pages missing from an explicit
`nav` are still built, with a warning.

## Search

With `search: true` (the default), every page is split into sections at its headings and
written to `_mdbake/search_index.js`. In the browser, the index is loaded the first time the
search box is used, and searching runs in a Web Worker, so large pages never block typing.
Results link straight to the matching heading. Press `/` or `Ctrl/Cmd+K` to focus the box.

The search works on sites opened from disk (`file://`) too: the index is loaded with a
`<script>` tag rather than `fetch()`, and the worker is created from a Blob URL. If a browser
refuses to start the worker, the search runs on the page instead.

Add `search: false` to a page's frontmatter to keep it out of the index.

## Middleware

A middleware is any module or class exposing some of these hooks. A hook returns the new
value, or `None` to keep the current one. Middleware runs in config order.

| Hook | Typical use |
|---|---|
| `on_config(config)` | tweak settings (`return config.replace(...)`) |
| `on_files(files, *, config)` | add/remove files |
| `on_page_source(page, *, site)` | frontmatter processing; set `page.skip = True` to drop a page |
| `on_page_markdown(markdown, *, page, site)` | macros, text substitution |
| `on_page_html(html, *, page, site)` | post-process HTML |
| `on_nav(nav, *, site)` | reorder or hide navigation |
| `on_page_context(ctx, *, page, site)` | extra template variables |
| `on_post_build(*, site)` | sitemap, search index, ... |
| `md_setup(md)` | register markdown-it plugins |

Specs are dotted paths with an optional `:Attr`. Classes are instantiated with `options`
as keyword arguments; modules are used as-is. The config file's directory is on
`sys.path`, so a local `myhooks.py` next to `mdbake.yml` can be loaded directly:

```python
# myhooks.py
from datetime import date


class Stamp:
    def __init__(self, format="%Y-%m-%d"):
        self.format = format

    def on_page_html(self, html, *, page, site):
        return html + f"<p><small>Built {date.today():{self.format}}</small></p>"
```

```yaml
middleware:
  - path: myhooks:Stamp
    options: {format: "%d.%m.%Y"}
```

Built-ins:

- `mdbake.builtin.draft`: drops pages with `draft: true` (`mdbake.builtin.draft:Draft` with `include_drafts: true` keeps them)
- `mdbake.builtin.frontmatter_defaults:FrontmatterDefaults`: options `defaults`, `required`, `strict`

## Theming

The built-in theme (in `src/mdbake/theme/`) has a left sidebar nav, an "On this page" TOC,
prev/next links, light/dark mode via `prefers-color-scheme`, and a mobile layout. To customize
it, set `templates_dir` and put any of `base.html`, `nav.html`, `toc.html`, `style.css` or
`search.js` there; missing files fall back to the built-in ones.

Template context: `page`, `nav`, `toc`, `config`, `site_name`, `extra`, `base_url`,
`assets_url`, `home_url`, and `url(target)` to make a site-root URL relative to the current page.

## Development

```bash
pytest
mdbake build -d tests/fixtures/docs -o /tmp/fixture-site
```

Project layout:

```
src/mdbake/
  cli.py          command line interface
  config.py       mdbake.yml loading
  files.py        file discovery, source → output paths
  frontmatter.py  YAML frontmatter splitting
  markdown.py     markdown-it setup, heading ids, highlighting
  links.py        relative link rewriting
  toc.py          table of contents
  search.py       search index (sections per heading)
  nav.py          navigation (explicit / auto), prev/next
  page.py         Page model
  middleware.py   middleware loader and pipeline
  builder.py      build orchestration
  builtin/        bundled middleware
  theme/          default templates, CSS and search.js
```

See [BUILDME.md](BUILDME.md) for the original design plan.
