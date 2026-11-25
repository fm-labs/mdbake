from pathlib import Path

from mdbake.files import File, dest_path_for
from mdbake.nav import Link, Section, build_nav
from mdbake.page import Page


def make_pages(spec: dict[str, dict]) -> list[Page]:
    return [Page(file=File(p, Path("/d") / p, dest_path_for(p)), meta=dict(meta)) for p, meta in spec.items()]


PAGES = {
    "index.md": {},
    "zeta.md": {},
    "alpha.md": {},
    "guide/index.md": {"title": "The Guide"},
    "guide/b.md": {},
    "guide/a.md": {"nav_order": 5},
    "guide/first.md": {"nav_order": 1},
    "api/index.md": {},
}


def titles(items):
    out = []
    for item in items:
        if isinstance(item, Section):
            out.append((item.title, titles(item.children)))
        else:
            out.append(item.title)
    return out


def test_auto_nav():
    pages = make_pages(PAGES)
    nav = build_nav(None, pages)
    # index first; pages before sections; nav_order wins; lone index collapses to a page
    assert titles(nav.items) == [
        "Home", "Alpha", "Zeta", "Api",
        ("The Guide", ["First", "A", "B"]),
    ]
    guide = nav.items[-1]
    by_src = {p.src_path: p for p in pages}
    assert guide.page is by_src["guide/index.md"]
    assert by_src["guide/a.md"].parent is guide
    assert by_src["guide/a.md"].ancestors == [guide]
    assert [p.src_path for p in nav.pages] == [
        "index.md", "alpha.md", "zeta.md", "api/index.md",
        "guide/index.md", "guide/first.md", "guide/a.md", "guide/b.md",
    ]


def test_prev_next():
    pages = make_pages(PAGES)
    nav = build_nav(None, pages)
    first, second = nav.pages[0], nav.pages[1]
    assert first.previous_page is None and first.next_page is second
    assert second.previous_page is first
    assert nav.pages[-1].next_page is None


def test_explicit_nav():
    pages = make_pages(PAGES)
    warnings = []
    config_nav = [
        {"Start": "index.md"},
        {"Guide": ["guide/first.md", {"Custom": "guide/b.md"}, "guide/missing.md"]},
        {"GitHub": "https://github.com/x"},
        "zeta.md",
        42,
    ]
    nav = build_nav(config_nav, pages, warn=warnings.append)
    assert titles(nav.items) == ["Start", ("Guide", ["First", "Custom"]), "GitHub", "Zeta"]
    assert isinstance(nav.items[2], Link) and nav.items[2].url == "https://github.com/x"
    assert [p.src_path for p in nav.pages] == ["index.md", "guide/first.md", "guide/b.md", "zeta.md"]
    assert len(warnings) == 2
    assert "guide/missing.md" in warnings[0]
    by_src = {p.src_path: p for p in pages}
    assert by_src["guide/b.md"].parent is nav.items[1]
    assert by_src["alpha.md"].next_page is None  # not in nav
