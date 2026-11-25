"""Discover Markdown pages and static assets; map source paths to output paths."""

from __future__ import annotations

import os
import posixpath
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

PAGE_SUFFIXES = (".md", ".markdown")


def is_page_path(src_path: str) -> bool:
    return src_path.lower().endswith(PAGE_SUFFIXES)


def dest_path_for(src_path: str, *, dir_has_index_md: bool = False) -> str:
    """Map a source path (posix, relative to docs_dir) to its output path.

    ``foo/bar.md`` -> ``foo/bar.html``; ``foo/index.md`` and ``foo/README.md`` ->
    ``foo/index.html`` (``README.md`` only when there is no ``index.md`` next to it).
    Non-page files keep their path.
    """
    if not is_page_path(src_path):
        return src_path
    directory, name = posixpath.split(src_path)
    stem = name.rsplit(".", 1)[0]
    if stem.lower() == "index" or (stem.lower() == "readme" and not dir_has_index_md):
        return posixpath.join(directory, "index.html")
    return posixpath.join(directory, stem + ".html")


@dataclass(eq=False)
class File:
    src_path: str  # posix path relative to docs_dir
    abs_src_path: Path
    dest_path: str  # posix path relative to site_dir

    @property
    def url(self) -> str:
        """Site-root-relative URL (unquoted)."""
        return self.dest_path

    @property
    def is_page(self) -> bool:
        return is_page_path(self.src_path)

    @property
    def is_index(self) -> bool:
        return self.is_page and posixpath.basename(self.dest_path) == "index.html"

    def __repr__(self) -> str:
        return f"File({self.src_path!r} -> {self.dest_path!r})"


class Files:
    """Ordered collection of :class:`File` objects keyed by ``src_path``."""

    def __init__(self, files: Iterable[File] = ()):
        self._files: dict[str, File] = {}
        for f in files:
            self.add(f)

    def __iter__(self) -> Iterator[File]:
        return iter(list(self._files.values()))

    def __len__(self) -> int:
        return len(self._files)

    def __contains__(self, src_path: object) -> bool:
        return src_path in self._files

    def get(self, src_path: str) -> File | None:
        return self._files.get(src_path)

    def add(self, file: File) -> None:
        self._files[file.src_path] = file

    def remove(self, file: File | str) -> None:
        key = file if isinstance(file, str) else file.src_path
        self._files.pop(key, None)

    def pages(self) -> list[File]:
        return [f for f in self._files.values() if f.is_page]

    def assets(self) -> list[File]:
        return [f for f in self._files.values() if not f.is_page]


def discover(docs_dir: Path, *, exclude: Iterable[Path] = ()) -> Files:
    """Walk ``docs_dir`` recursively, skipping dotfiles/dot-dirs and ``exclude`` dirs."""
    docs_dir = Path(docs_dir).resolve()
    excluded = {Path(p).resolve() for p in exclude}
    result = Files()
    for root, dirs, names in os.walk(docs_dir):
        root_path = Path(root)
        dirs[:] = sorted(
            d for d in dirs if not d.startswith(".") and (root_path / d).resolve() not in excluded
        )
        lowered = {n.lower() for n in names}
        has_index = any(f"index{s}" in lowered for s in PAGE_SUFFIXES)
        for name in sorted(names):
            if name.startswith("."):
                continue
            abs_path = root_path / name
            src_path = abs_path.relative_to(docs_dir).as_posix()
            dest = dest_path_for(src_path, dir_has_index_md=has_index)
            result.add(File(src_path=src_path, abs_src_path=abs_path, dest_path=dest))
    return result
