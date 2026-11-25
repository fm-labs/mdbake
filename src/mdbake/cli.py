"""Command line interface: ``mdbake build``."""

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
    level = logging.ERROR if quiet else logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)-7s %(message)s", level=level)
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


if __name__ == "__main__":  # pragma: no cover
    main()
