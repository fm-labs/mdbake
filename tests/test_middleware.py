import sys
import types

import pytest

from mdbake.builtin import draft
from mdbake.builtin.frontmatter_defaults import FrontmatterDefaults
from mdbake.middleware import MiddlewareError, Pipeline, import_object, load_middleware


@pytest.fixture
def hooks_module(monkeypatch):
    mod = types.ModuleType("fake_hooks")

    class Upper:
        def __init__(self, suffix=""):
            self.suffix = suffix

        def on_page_markdown(self, markdown, *, page, site):
            return markdown.upper() + self.suffix

    def on_page_markdown(markdown, *, page, site):
        return None  # keep

    mod.Upper = Upper
    mod.on_page_markdown = on_page_markdown
    monkeypatch.setitem(sys.modules, "fake_hooks", mod)
    return mod


def test_import_object_forms(hooks_module):
    assert import_object("fake_hooks") is hooks_module
    assert import_object("fake_hooks:Upper") is hooks_module.Upper
    assert import_object("fake_hooks.Upper") is hooks_module.Upper
    with pytest.raises(MiddlewareError):
        import_object("fake_hooks:Nope")
    with pytest.raises(MiddlewareError):
        import_object("does_not_exist_xyz")


def test_load_middleware(hooks_module):
    assert load_middleware("fake_hooks") is hooks_module
    inst = load_middleware({"path": "fake_hooks:Upper", "options": {"suffix": "!"}})
    assert inst.suffix == "!"
    with pytest.raises(MiddlewareError):
        load_middleware({"path": "fake_hooks", "options": {"x": 1}})
    with pytest.raises(MiddlewareError):
        load_middleware({"path": "fake_hooks:Upper", "options": {"bad": 1}})
    with pytest.raises(MiddlewareError):
        load_middleware(123)


def test_pipeline_order_and_none_passthrough(hooks_module):
    calls = []

    class Rec:
        def __init__(self, tag):
            self.tag = tag

        def on_page_markdown(self, markdown, *, page, site):
            calls.append(self.tag)
            return markdown + self.tag

    pipe = Pipeline([Rec("a"), hooks_module, Rec("b"), hooks_module.Upper("?")])
    assert pipe.run("on_page_markdown", "x", page=None, site=None) == "XAB?"
    assert calls == ["a", "b"]
    assert pipe.run("on_nav", "unchanged", site=None) == "unchanged"


def test_pipeline_wraps_errors():
    class Boom:
        def on_post_build(self, *, site):
            raise RuntimeError("bang")

    with pytest.raises(MiddlewareError, match="Boom.on_post_build"):
        Pipeline([Boom()]).notify("on_post_build", site=None)


class FakePage:
    def __init__(self, meta):
        self.meta, self.skip, self.src_path = meta, False, "p.md"


class FakeSite:
    def __init__(self):
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)


def test_draft_builtin():
    page = FakePage({"draft": True})
    Pipeline([draft]).run("on_page_source", page, site=None)
    assert page.skip
    page = FakePage({"draft": True})
    Pipeline([draft.Draft(include_drafts=True)]).run("on_page_source", page, site=None)
    assert not page.skip


def test_frontmatter_defaults_builtin():
    site = FakeSite()
    mw = FrontmatterDefaults(defaults={"author": "Team", "tags": []}, required=["title"])
    page = FakePage({"author": "Me"})
    mw.on_page_source(page, site=site)
    assert page.meta == {"author": "Me", "tags": []}
    assert len(site.warnings) == 1 and "title" in site.warnings[0]
    with pytest.raises(ValueError):
        FrontmatterDefaults(required=["title"], strict=True).on_page_source(FakePage({}), site=site)
