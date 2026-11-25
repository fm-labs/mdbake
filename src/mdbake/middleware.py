"""Middleware loading and the hook pipeline.

A middleware is any object (module, class instance, ...) exposing some of the hook
methods below. Hooks that transform an item return the new value, or ``None`` to
keep the item unchanged. Middleware runs in config order.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from markdown_it import MarkdownIt

    from .config import Config

HOOKS = (
    "on_config",         # (config) -> config
    "on_files",          # (files, *, config) -> files
    "on_page_source",    # (page, *, site) -> page   (meta + markdown available; set page.skip)
    "on_page_markdown",  # (markdown, *, page, site) -> str
    "on_page_html",      # (html, *, page, site) -> str
    "on_nav",            # (nav, *, site) -> nav
    "on_page_context",   # (ctx, *, page, site) -> dict
    "on_post_build",     # (*, site) -> None
)


class MiddlewareError(Exception):
    pass


def import_object(path: str) -> Any:
    """Import ``pkg.mod``, ``pkg.mod:attr`` or ``pkg.mod.attr``."""
    if ":" in path:
        module_name, attr = path.split(":", 1)
    else:
        try:
            return importlib.import_module(path)
        except ModuleNotFoundError as exc:
            if "." not in path or (exc.name and not path.startswith(exc.name)):
                raise MiddlewareError(f"cannot import middleware '{path}': {exc}") from exc
            module_name, attr = path.rsplit(".", 1)
    try:
        obj: Any = importlib.import_module(module_name)
    except ImportError as exc:
        raise MiddlewareError(f"cannot import middleware '{path}': {exc}") from exc
    for part in attr.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError as exc:
            raise MiddlewareError(f"middleware '{path}': no attribute '{part}'") from exc
    return obj


def load_middleware(spec: str | dict) -> Any:
    """Load one middleware from ``"dotted.path[:Attr]"`` or ``{path, options}``.

    Classes are instantiated with ``options`` as keyword arguments; anything else
    (modules, objects) is used as-is.
    """
    if isinstance(spec, str):
        path, options = spec, {}
    elif isinstance(spec, dict) and isinstance(spec.get("path"), str):
        path, options = spec["path"], spec.get("options") or {}
        if not isinstance(options, dict):
            raise MiddlewareError(f"middleware '{path}': options must be a mapping")
    else:
        raise MiddlewareError(f"invalid middleware spec: {spec!r}")

    target = import_object(path)
    if inspect.isclass(target):
        try:
            return target(**options)
        except TypeError as exc:
            raise MiddlewareError(f"middleware '{path}': {exc}") from exc
    if options:
        raise MiddlewareError(f"middleware '{path}': options given but target is not a class")
    return target


def _name(mw: Any) -> str:
    if inspect.ismodule(mw):
        return mw.__name__
    return f"{type(mw).__module__}.{type(mw).__qualname__}"


class Pipeline:
    def __init__(self, middlewares: Iterable[Any] = ()):
        self.middlewares = list(middlewares)

    @classmethod
    def from_config(cls, config: Config) -> Pipeline:
        # Allow local hook modules next to the config file.
        if config.config_file is not None:
            config_dir = str(Path(config.config_file).parent)
            if config_dir not in sys.path:
                sys.path.insert(0, config_dir)
        return cls(load_middleware(spec) for spec in config.middleware)

    def _call(self, mw: Any, hook: str, *args: Any, **kwargs: Any) -> Any:
        fn = getattr(mw, hook, None)
        if fn is None:
            return None
        try:
            return fn(*args, **kwargs)
        except MiddlewareError:
            raise
        except Exception as exc:
            raise MiddlewareError(f"{_name(mw)}.{hook} failed: {exc!r}") from exc

    def run(self, hook: str, item: Any, **ctx: Any) -> Any:
        """Pass ``item`` through every middleware's ``hook``; ``None`` keeps it."""
        for mw in self.middlewares:
            result = self._call(mw, hook, item, **ctx)
            if result is not None:
                item = result
        return item

    def notify(self, hook: str, **ctx: Any) -> None:
        for mw in self.middlewares:
            self._call(mw, hook, **ctx)

    def md_setup(self, md: MarkdownIt) -> None:
        for mw in self.middlewares:
            self._call(mw, "md_setup", md)
