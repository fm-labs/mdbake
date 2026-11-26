"""Load ``mdbake.yml`` into a frozen :class:`Config` dataclass."""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("mdbake")

DEFAULT_CONFIG_NAMES = ("mdbake.yml", "mdbake.yaml")


class ConfigError(Exception):
    """Raised for a missing or invalid configuration file."""


@dataclass(frozen=True)
class Config:
    site_name: str = "Documentation"
    docs_dir: Path = Path("docs")
    site_dir: Path = Path("site")
    templates_dir: Path | None = None
    nav: list | None = None
    middleware: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    toc_depth: int = 3
    search: bool = True
    pygments_style: str = "default"
    pygments_dark_style: str = "monokai"
    config_file: Path | None = None

    def replace(self, **changes: Any) -> Config:
        """Return a copy with ``changes`` applied (for ``on_config`` middleware)."""
        return dataclasses.replace(self, **changes)


_KEYS = {f.name for f in dataclasses.fields(Config)} - {"config_file"}


def _resolve(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def find_config_file(directory: Path | None = None) -> Path | None:
    directory = directory or Path.cwd()
    for name in DEFAULT_CONFIG_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def load_config(
    path: str | Path | None = None,
    *,
    docs_dir: str | Path | None = None,
    site_dir: str | Path | None = None,
) -> Config:
    """Load configuration.

    Paths inside the config file are relative to the file's directory; ``docs_dir``
    and ``site_dir`` overrides (from the CLI) are relative to the current directory.
    Without a config file, defaults are used relative to the current directory.
    """
    cwd = Path.cwd()
    if path is None:
        path = find_config_file(cwd)

    data: dict[str, Any] = {}
    base = cwd
    config_file = None
    if path is not None:
        config_file = Path(path).expanduser().resolve()
        if not config_file.is_file():
            raise ConfigError(f"Config file not found: {config_file}")
        try:
            raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {config_file}: {exc}") from exc
        raw = raw or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_file}: top level must be a mapping")
        unknown = sorted(set(raw) - _KEYS)
        if unknown:
            log.warning("Unknown config keys ignored: %s", ", ".join(unknown))
        data = {k: v for k, v in raw.items() if k in _KEYS}
        base = config_file.parent

    defaults = Config()

    site_name = data.get("site_name", defaults.site_name)
    if not isinstance(site_name, str):
        raise ConfigError("'site_name' must be a string")

    nav = data.get("nav")
    if nav is not None and not isinstance(nav, list):
        raise ConfigError("'nav' must be a list")

    middleware = data.get("middleware") or []
    if not isinstance(middleware, list):
        raise ConfigError("'middleware' must be a list")

    extra = data.get("extra") or {}
    if not isinstance(extra, dict):
        raise ConfigError("'extra' must be a mapping")

    toc_depth = data.get("toc_depth", defaults.toc_depth)
    if not isinstance(toc_depth, int) or not 1 <= toc_depth <= 6:
        raise ConfigError("'toc_depth' must be an integer between 1 and 6")

    search = data.get("search", defaults.search)
    if not isinstance(search, bool):
        raise ConfigError("'search' must be true or false")

    templates_dir = data.get("templates_dir")

    return Config(
        site_name=site_name,
        docs_dir=_resolve(docs_dir, cwd) if docs_dir else _resolve(data.get("docs_dir", "docs"), base),
        site_dir=_resolve(site_dir, cwd) if site_dir else _resolve(data.get("site_dir", "site"), base),
        templates_dir=_resolve(templates_dir, base) if templates_dir else None,
        nav=nav,
        middleware=middleware,
        extra=extra,
        toc_depth=toc_depth,
        search=search,
        pygments_style=str(data.get("pygments_style", defaults.pygments_style)),
        pygments_dark_style=str(data.get("pygments_dark_style", defaults.pygments_dark_style)),
        config_file=config_file,
    )
