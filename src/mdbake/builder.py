"""Orchestrates the build pipeline."""

from __future__ import annotations

import logging
import posixpath
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import jinja2

from .config import Config
from .files import Files, discover
from .frontmatter import FrontmatterError, split_frontmatter
from .links import LinkRef, is_external, relative_url
from .markdown import create_markdown, pygments_css
from .middleware import Pipeline
from .nav import Navigation, build_nav
from .page import Page
from .toc import build_toc

log = logging.getLogger("mdbake")

THEME_DIR = Path(__file__).parent / "theme"
ASSETS_DIR = "_mdbake"
_ID_RE = re.compile(r"""\sid\s*=\s*["']([^"']+)["']""")


class BuildError(Exception):
    pass


@dataclass(eq=False)
class Site:
    """Shared build state handed to middleware as ``site``."""

    config: Config
    files: Files
    pipeline: Pipeline
    pages: list[Page] = field(default_factory=list)
    nav: Navigation | None = None
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        log.warning(message)

    def get_page(self, src_path: str) -> Page | None:
        for page in self.pages:
            if page.src_path == src_path:
                return page
        return None


def build(config: Config, *, pipeline: Pipeline | None = None, clean: bool = False) -> Site:
    pipeline = pipeline if pipeline is not None else Pipeline.from_config(config)

    # 1. config
    config = pipeline.run("on_config", config)
    docs_dir = Path(config.docs_dir)
    if not docs_dir.is_dir():
        raise BuildError(f"docs_dir does not exist: {docs_dir}")

    # 2. files
    files = discover(docs_dir, exclude=[config.site_dir])
    files = pipeline.run("on_files", files, config=config)
    site = Site(config=config, files=files, pipeline=pipeline)

    # 3. read pages + frontmatter
    for file in files.pages():
        try:
            text = file.abs_src_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            site.warn(f"{file.src_path}: cannot read: {exc}")
            files.remove(file)
            continue
        try:
            meta, body = split_frontmatter(text)
        except FrontmatterError as exc:
            site.warn(f"{file.src_path}: {exc}")
            meta, body = {}, text
        page = pipeline.run("on_page_source", Page(file=file, meta=meta, markdown=body), site=site)
        if page.skip:
            log.debug("Skipping %s", file.src_path)
            files.remove(file)
            continue
        site.pages.append(page)

    # 4. nav (titles resolve lazily, so H1 titles found while rendering show up)
    site.nav = pipeline.run("on_nav", build_nav(config.nav, site.pages, warn=site.warn), site=site)
    if config.nav:
        in_nav = {id(p) for p in site.nav.pages}
        for page in site.pages:
            if id(page) not in in_nav:
                site.warn(f"{page.src_path}: page exists but is not in nav")

    # 5. render markdown
    md = create_markdown()
    pipeline.md_setup(md)
    link_refs: list[LinkRef] = []
    for page in site.pages:
        markdown = pipeline.run("on_page_markdown", page.markdown, page=page, site=site)
        env: dict[str, Any] = {"page": page, "site": site, "files": site.files}
        html = md.render(markdown, env)
        headings = env.get("headings", [])
        page.h1_title = next((title for level, title, _ in headings if level == 1 and title), None)
        page.toc = build_toc(headings, config.toc_depth)
        link_refs.extend(env.get("link_refs", []))
        page.html = pipeline.run("on_page_html", html, page=page, site=site)
        page.anchors = set(_ID_RE.findall(page.html))

    # 6. validate links + anchors
    pages_by_src = {p.src_path: p for p in site.pages}
    for ref in link_refs:
        if ref.broken:
            site.warn(f"{ref.source.src_path}: broken link '{ref.url}'")
        elif ref.fragment and ref.target is not None:
            target = pages_by_src.get(ref.target.src_path)
            if target is not None and ref.fragment not in target.anchors:
                site.warn(
                    f"{ref.source.src_path}: link '{ref.url}' points to missing anchor "
                    f"'#{ref.fragment}' in {target.src_path}"
                )

    # 7. templates + output
    site_dir = Path(config.site_dir)
    if clean:
        _clean_site_dir(site_dir, docs_dir)
    _write_site(site, site_dir)

    # 8. post build
    pipeline.notify("on_post_build", site=site)
    log.info("Built %d pages into %s", len(site.pages), site_dir)
    return site


def _clean_site_dir(site_dir: Path, docs_dir: Path) -> None:
    sd, dd = site_dir.resolve(), docs_dir.resolve()
    forbidden = {dd, Path.cwd().resolve(), Path.home().resolve(), Path(sd.anchor)}
    if sd in forbidden or sd in dd.parents:
        raise BuildError(f"refusing to clean site_dir {sd}: it contains docs_dir or is unsafe")
    if sd.exists():
        shutil.rmtree(sd)


def make_jinja_env(config: Config) -> jinja2.Environment:
    loaders: list[jinja2.BaseLoader] = []
    if config.templates_dir is not None:
        loaders.append(jinja2.FileSystemLoader(str(config.templates_dir)))
    loaders.append(jinja2.FileSystemLoader(str(THEME_DIR)))
    return jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders),
        autoescape=jinja2.select_autoescape(["html", "htm", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def page_context(page: Page, site: Site) -> dict[str, Any]:
    def url(target: str) -> str:
        if is_external(target):
            return target
        return quote(relative_url(target, page.url), safe="/#")

    base_url = posixpath.relpath(".", posixpath.dirname(page.url) or ".")
    toc = page.toc
    if len(toc) == 1 and toc[0].level == 1:  # page H1 is the title; show its children
        toc = toc[0].children
    home = site.get_page("index.md") or site.get_page("README.md")
    home_url = home.url if home else (site.nav.pages[0].url if site.nav and site.nav.pages else "index.html")
    return {
        "config": site.config,
        "site_name": site.config.site_name,
        "extra": site.config.extra,
        "page": page,
        "nav": site.nav,
        "toc": toc,
        "url": url,
        "base_url": base_url,
        "assets_url": f"{base_url}/{ASSETS_DIR}",
        "home_url": url(home_url),
    }


def _write_site(site: Site, site_dir: Path) -> None:
    config = site.config
    env = make_jinja_env(config)
    try:
        template = env.get_template("base.html")
    except jinja2.TemplateError as exc:
        raise BuildError(f"cannot load template: {exc}") from exc

    for page in site.pages:
        ctx = site.pipeline.run("on_page_context", page_context(page, site), page=page, site=site)
        out = site_dir / page.file.dest_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(template.render(ctx), encoding="utf-8")

    for asset in site.files.assets():
        out = site_dir / asset.dest_path
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset.abs_src_path, out)

    theme_out = site_dir / ASSETS_DIR
    theme_out.mkdir(parents=True, exist_ok=True)
    style = THEME_DIR / "style.css"
    if config.templates_dir is not None and (config.templates_dir / "style.css").is_file():
        style = config.templates_dir / "style.css"
    shutil.copyfile(style, theme_out / "style.css")
    (theme_out / "pygments.css").write_text(
        pygments_css(config.pygments_style, config.pygments_dark_style), encoding="utf-8"
    )
