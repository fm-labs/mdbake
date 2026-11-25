# Middleware

Middleware is any module or class exposing some of these hooks. A hook returns the new
value, or `None` to keep it unchanged; middleware runs in config order.

| Hook | Use |
|---|---|
| `on_config(config)` | tweak settings (`config.replace(...)`) |
| `on_files(files, *, config)` | add/remove files |
| `on_page_source(page, *, site)` | frontmatter processing; set `page.skip = True` to drop |
| `on_page_markdown(markdown, *, page, site)` | text substitution, macros |
| `on_page_html(html, *, page, site)` | post-process HTML |
| `on_nav(nav, *, site)` | reorder/hide navigation |
| `on_page_context(ctx, *, page, site)` | extra template variables |
| `on_post_build(*, site)` | sitemap, search index, ... |
| `md_setup(md)` | register markdown-it plugins |

## Configuring

```yaml
middleware:
  - mdbake.builtin.draft              # a module
  - myhooks:Stamp                     # a class, instantiated without options
  - path: myhooks:Stamp
    options: {format: "%Y-%m-%d"}     # passed as keyword arguments
```

The config file's directory is on `sys.path`, so a local `myhooks.py` just works.

## Example

```python
from datetime import date


class Stamp:
    def __init__(self, format="%Y-%m-%d"):
        self.format = format

    def on_page_html(self, html, *, page, site):
        return html + f"<p><small>Built {date.today():{self.format}}</small></p>"
```

## Built-ins

- `mdbake.builtin.draft` — drops pages with `draft: true` (`Draft(include_drafts=True)` to keep them)
- `mdbake.builtin.frontmatter_defaults:FrontmatterDefaults` — `defaults`, `required`, `strict` options

Back to [the configuration](configuration.md#navigation).
