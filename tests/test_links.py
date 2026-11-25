from pathlib import Path

import pytest

from mdbake.files import File, Files, dest_path_for
from mdbake.links import relative_url, resolve_link
from mdbake.markdown import create_markdown
from mdbake.page import Page


def make_files(*paths: str) -> Files:
    return Files(File(p, Path("/docs") / p, dest_path_for(p)) for p in paths)


FILES = make_files("index.md", "a.md", "sub/index.md", "sub/b.md", "sub/deep/c.md", "img/x.png", "my file.md")


@pytest.mark.parametrize(
    "source, url, expected",
    [
        ("index.md", "a.md", "a.html"),
        ("index.md", "sub/b.md", "sub/b.html"),
        ("sub/b.md", "../a.md", "../a.html"),
        ("sub/b.md", "../index.md", "../index.html"),
        ("sub/deep/c.md", "../../a.md#x", "../../a.html#x"),
        ("sub/deep/c.md", "../b.md", "../b.html"),
        ("sub/b.md", "./deep/c.md", "deep/c.html"),
        ("index.md", "sub/", "sub/index.html"),
        ("sub/b.md", "../img/x.png", "../img/x.png"),
        ("index.md", "my%20file.md", "my%20file.html"),
        ("sub/b.md", "b.md?x=1#y", "b.html?x=1#y"),
    ],
)
def test_resolve_relative(source, url, expected):
    new, ref = resolve_link(url, FILES.get(source), FILES)
    assert new == expected
    assert ref is not None and not ref.broken


@pytest.mark.parametrize("url", ["https://example.com/a.md", "mailto:x@y.z", "/abs/a.md", "//cdn/x.js"])
def test_external_untouched(url):
    assert resolve_link(url, FILES.get("index.md"), FILES) == (url, None)


def test_same_page_anchor():
    src = FILES.get("sub/b.md")
    new, ref = resolve_link("#frag", src, FILES)
    assert new == "#frag"
    assert ref.target is src and ref.fragment == "frag"


@pytest.mark.parametrize("url", ["missing.md", "../../outside.md", "sub/nothing/"])
def test_broken(url):
    new, ref = resolve_link(url, FILES.get("sub/b.md"), FILES)
    assert new == url
    assert ref.broken


def test_relative_url():
    assert relative_url("a.html", "index.html") == "a.html"
    assert relative_url("index.html", "x/y/z.html") == "../../index.html"
    assert relative_url("x/y.html", "x/y.html") == "y.html"


def test_rewrite_in_markdown():
    md = create_markdown()
    page = Page(file=FILES.get("sub/b.md"))
    env = {"page": page, "files": FILES}
    html = md.render("[a](../a.md) ![x](../img/x.png) [e](https://e.com/b.md) [m](nope.md)", env)
    assert 'href="../a.html"' in html
    assert 'src="../img/x.png"' in html
    assert 'href="https://e.com/b.md"' in html
    assert 'href="nope.md"' in html
    assert [r.broken for r in env["link_refs"]] == [False, False, True]
