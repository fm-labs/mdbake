# mdbake

A minimal Markdown → HTML documentation generator.

- Reads all `*.md` files from `docs_dir` recursively
- Renders GitHub-flavored Markdown (tables, task lists, strikethrough, autolinks, footnotes)
- Builds navigation from [`mdbake.yml`](guide/configuration.md#navigation) or the directory tree
- Rewrites links between `.md` files to relative `.html` links, warning on broken targets and anchors
- Extensible through a [middleware chain](guide/middleware.md)

## Quick start

```bash
pip install -e .
mdbake build                 # uses ./mdbake.yml if present
mdbake build -d docs -o site --strict
mdbake watch                 # live preview on http://127.0.0.1:8000
mdbake serve                 # serve the built site
```

Open `site/index.html` directly from disk: all links are relative.
