"""Command line interface: ``mdbake build``, ``mdbake serve`` and ``mdbake watch``."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from . import __version__
from .builder import BuildError, build as build_site
from .config import ConfigError, load_config
from .middleware import MiddlewareError


@click.group()
@click.version_option(__version__, prog_name="mdbake")
def main() -> None:
    """mdbake - a minimal Markdown to HTML documentation generator."""


@main.command()
@click.option("-f", "--config", "config_file", type=click.Path(dir_okay=False, path_type=Path),
              help="Config file (default: ./mdbake.yml if present).")
@click.option("-d", "--docs-dir", type=click.Path(file_okay=False, path_type=Path),
              help="Directory with Markdown sources (overrides config).")
@click.option("-o", "--site-dir", type=click.Path(file_okay=False, path_type=Path),
              help="Output directory (overrides config).")
@click.option("--clean", is_flag=True, help="Delete site_dir before building.")
@click.option("-s", "--strict", is_flag=True, help="Exit with an error if there were warnings.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
@click.option("-q", "--quiet", is_flag=True, help="Only show errors.")
def build(config_file: Path | None, docs_dir: Path | None, site_dir: Path | None,
          clean: bool, strict: bool, verbose: bool, quiet: bool) -> None:
    """Build the documentation site."""
    _setup_logging(verbose, quiet)
    try:
        config = load_config(config_file, docs_dir=docs_dir, site_dir=site_dir)
        site = build_site(config, clean=clean)
    except (ConfigError, BuildError, MiddlewareError) as exc:
        raise click.ClickException(str(exc)) from exc
    if site.warnings:
        msg = f"{len(site.warnings)} warning(s)"
        if strict:
            raise click.ClickException(f"Aborted: {msg} in strict mode")
        logging.getLogger("mdbake").info(msg)



_config_option = click.option("-f", "--config", "config_file", type=click.Path(dir_okay=False, path_type=Path),
                              help="Config file (default: ./mdbake.yml if present).")
_host_option = click.option("--host", default="127.0.0.1", show_default=True, help="Address to listen on.")
_port_option = click.option("-p", "--port", default=8000, show_default=True, type=click.IntRange(0, 65535),
                            help="Port to listen on.")


def _setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    level = logging.ERROR if quiet else logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)-7s %(message)s", level=level)


@main.command("serve")
@_config_option
@click.option("-o", "--site-dir", type=click.Path(file_okay=False, path_type=Path),
              help="Directory to serve (overrides config).")
@_host_option
@_port_option
def serve_site(config_file: Path | None, site_dir: Path | None, host: str, port: int) -> None:
    """Serve the built site over HTTP (no rebuilding)."""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    _setup_logging()
    try:
        config = load_config(config_file, site_dir=site_dir)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc
    root = config.site_dir
    if not root.is_dir():
        raise click.ClickException(f"Site directory not found: {root} (run 'mdbake build' first)")

    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    try:
        httpd = ThreadingHTTPServer((host, port), handler)
    except OSError as exc:
        raise click.ClickException(f"Cannot listen on {host}:{port}: {exc}") from exc
    with httpd:
        click.echo(f"Serving {root} at http://{host}:{httpd.server_port}/ (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


@main.command("watch")
@_config_option
@click.option("-d", "--docs-dir", type=click.Path(file_okay=False, path_type=Path),
              help="Directory with Markdown sources (overrides config).")
@click.option("-o", "--site-dir", type=click.Path(file_okay=False, path_type=Path),
              help="Output directory (overrides config).")
@_host_option
@_port_option
@click.option("--open", "open_browser", is_flag=True, help="Open the site in a web browser.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
def watch_docs(config_file: Path | None, docs_dir: Path | None, site_dir: Path | None,
               host: str, port: int, open_browser: bool, verbose: bool) -> None:
    """Build the site, serve it, and rebuild and reload the browser on changes."""
    from livereload import Server

    _setup_logging(verbose)
    log = logging.getLogger("mdbake")

    def load():
        return load_config(config_file, docs_dir=docs_dir, site_dir=site_dir)

    try:
        config = load()
        build_site(config)
    except (ConfigError, BuildError, MiddlewareError) as exc:
        raise click.ClickException(str(exc)) from exc

    def rebuild() -> None:
        # Re-read the config so edits to mdbake.yml apply; keep serving on errors.
        try:
            build_site(load())
        except (ConfigError, BuildError, MiddlewareError) as exc:
            log.error("Rebuild failed: %s", exc)

    logging.getLogger("livereload").propagate = False  # it has its own handler
    server = Server()
    watched = [config.docs_dir, config.config_file, config.templates_dir]
    for path in watched:
        if path is not None and path.exists():
            server.watch(str(path), rebuild, delay=0.2)
    server.serve(host=host, port=port, root=str(config.site_dir), open_url_delay=0 if open_browser else None,
                 debug=False)

if __name__ == "__main__":  # pragma: no cover
    main()
