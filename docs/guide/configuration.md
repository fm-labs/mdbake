---
title: Configuration
---
# Configuration file

`mdbake.yml` lives next to your project; paths in it are relative to the file.

| Key | Default | Meaning |
|---|---|---|
| `site_name` | `Documentation` | Shown in the top bar and page titles |
| `docs_dir` | `docs` | Markdown sources |
| `site_dir` | `site` | Output directory |
| `templates_dir` | — | Overrides `base.html`, `nav.html`, `toc.html`, `style.css` |
| `nav` | auto | Explicit navigation (see below) |
| `middleware` | `[]` | Middleware chain (see [Middleware](middleware.md)) |
| `toc_depth` | `3` | Deepest heading level in "On this page" |
| `extra` | `{}` | Free-form, passed to templates (`extra.lang` sets `<html lang>`) |

## Navigation

```yaml
nav:
  - Home: index.md
  - Guide:
      - guide/install.md        # title taken from the page
      - Usage: guide/usage.md   # explicit title
  - GitHub: https://github.com/example
```

Without `nav`, the directory tree is used: `index.md`/`README.md` first, then pages,
then sub-directories (whose `index.md` becomes the section link). Set `nav_order: <n>`
in frontmatter to reorder. Pages missing from an explicit `nav` are still built.

## Page titles

Explicit nav title → frontmatter `title` → first `# H1` → file name.
