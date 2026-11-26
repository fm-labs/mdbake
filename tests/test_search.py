import json

from mdbake.builder import build
from mdbake.config import Config, ConfigError, load_config
from mdbake.search import INDEX_GLOBAL, split_sections

import pytest


def _load_index(site_dir):
    text = (site_dir / "_mdbake/search_index.js").read_text(encoding="utf-8")
    prefix = f"window.{INDEX_GLOBAL}="
    assert text.startswith(prefix)
    return json.loads(text[len(prefix):].rstrip().rstrip(";"))


def test_split_sections():
    html = (
        "<p>Intro <em>text</em></p>"
        '<h2 id="a">First <code>one</code></h2><p>Alpha<br>beta</p><script>var x;</script>'
        "<h3>No id</h3><p>still a</p>"
        '<h2 id="b">Second</h2><ul><li>one</li><li>two</li></ul>'
    )
    sections = split_sections(html)
    assert [(s.title, s.anchor, s.text) for s in sections] == [
        ("", None, "Intro text"),
        ("First one", "a", "Alpha beta No id still a"),
        ("Second", "b", "one two"),
    ]


def test_index_written(fixture_docs, tmp_path):
    site_dir = tmp_path / "site"
    build(Config(docs_dir=fixture_docs, site_dir=site_dir, middleware=["mdbake.builtin.draft"]))
    assert (site_dir / "_mdbake/search.js").is_file()
    docs = _load_index(site_dir)["docs"]
    by_url = {d["u"]: d for d in docs}

    # leading H1 links to the page itself
    assert by_url["guide/usage.html"]["t"] == "Usage"
    running = by_url["guide/usage.html#running-it"]
    assert running == {"t": "Running it", "p": "Usage", "u": "guide/usage.html#running-it", "x": "Go deeper."}
    assert by_url["guide/install.html"]["p"] == "Installation"
    assert "world domination" in by_url["index.html#features"]["x"]
    assert not any(u.startswith("draft") for u in by_url)

    page = (site_dir / "guide/advanced/tuning.html").read_text()
    assert 'src="../../_mdbake/search.js" data-base="../.."' in page
    assert 'id="search-input"' in page


def test_search_opt_out(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\nhello")
    (docs / "hidden.md").write_text("---\nsearch: false\n---\n# Hidden\n\nsecret")
    (docs / "my page.md").write_text("# Spaced")
    site_dir = tmp_path / "site"
    build(Config(docs_dir=docs, site_dir=site_dir))
    urls = [d["u"] for d in _load_index(site_dir)["docs"]]
    assert "index.html" in urls
    assert "my%20page.html" in urls
    assert not any("hidden" in u for u in urls)


def test_search_disabled(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home")
    site_dir = tmp_path / "site"
    build(Config(docs_dir=docs, site_dir=site_dir, search=False))
    assert not (site_dir / "_mdbake/search_index.js").exists()
    assert not (site_dir / "_mdbake/search.js").exists()
    assert "search" not in (site_dir / "index.html").read_text()


def test_search_config_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mdbake.yml").write_text("search: false\n")
    assert load_config().search is False
    (tmp_path / "mdbake.yml").write_text("search: maybe\n")
    with pytest.raises(ConfigError):
        load_config()
