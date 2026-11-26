from pathlib import Path

from click.testing import CliRunner

from mdbake.builder import build
from mdbake.cli import main
from mdbake.config import Config, load_config


def test_build_fixture_site(fixture_docs, tmp_path):
    site_dir = tmp_path / "site"
    config = Config(docs_dir=fixture_docs, site_dir=site_dir, middleware=["mdbake.builtin.draft"])
    site = build(config)

    assert (site_dir / "index.html").is_file()
    assert (site_dir / "guide/index.html").is_file()
    assert (site_dir / "guide/advanced/tuning.html").is_file()
    assert (site_dir / "img/logo.svg").is_file()
    assert (site_dir / "_mdbake/style.css").is_file()
    assert (site_dir / "_mdbake/pygments.css").is_file()
    assert not (site_dir / "draft.html").exists()

    assert sorted(site.warnings) == sorted([
        "guide/install.md: broken link 'missing.md'",
        "guide/install.md: link 'usage.md#nope' points to missing anchor '#nope' in guide/usage.md",
    ])

    install = site.get_page("guide/install.md")
    assert install.title == "Installation"  # frontmatter beats H1
    assert site.get_page("guide/usage.md").title == "Usage"  # from H1

    tuning = (site_dir / "guide/advanced/tuning.html").read_text()
    assert 'href="../install.html#requirements-1"' in tuning
    assert 'href="../../_mdbake/style.css"' in tuning
    assert 'href="../../index.html"' in tuning
    assert 'class="active" aria-current="page">Tuning' in tuning

    index = (site_dir / "index.html").read_text()
    assert 'href="guide/usage.html#running-it"' in index
    assert '<meta name="description" content="Fixture home page">' in index
    assert 'rel="next"' in index and 'rel="prev"' not in index


def test_middleware_hooks_end_to_end(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Hi\n\nHello {{name}}.\n")
    (tmp_path / "myhooks.py").write_text(
        "events = []\n"
        "class Hooks:\n"
        "    def __init__(self, name): self.name = name\n"
        "    def on_config(self, config): events.append('config')\n"
        "    def on_files(self, files, *, config): events.append('files')\n"
        "    def on_page_source(self, page, *, site): page.meta['seen'] = True\n"
        "    def on_page_markdown(self, md, *, page, site): return md.replace('{{name}}', self.name)\n"
        "    def on_page_html(self, html, *, page, site): return html + '<!-- stamped -->'\n"
        "    def on_nav(self, nav, *, site): events.append('nav')\n"
        "    def on_page_context(self, ctx, *, page, site):\n"
        "        ctx['extra'] = {'lang': 'de'}\n"
        "        return ctx\n"
        "    def on_post_build(self, *, site):\n"
        "        (site.config.site_dir / 'done.txt').write_text(str(len(site.pages)))\n"
    )
    (tmp_path / "mdbake.yml").write_text(
        "site_name: Hooked\nmiddleware:\n  - path: myhooks:Hooks\n    options: {name: World}\n"
    )
    monkeypatch.chdir(tmp_path)
    build(load_config())
    html = (tmp_path / "site/index.html").read_text()
    assert "Hello World." in html
    assert "<!-- stamped -->" in html
    assert '<html lang="de">' in html
    assert (tmp_path / "site/done.txt").read_text() == "1"
    import myhooks
    assert myhooks.events == ["config", "files", "nav"]


def test_explicit_nav_warns_unlisted(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home")
    (docs / "other.md").write_text("# Other")
    site = build(Config(docs_dir=docs, site_dir=tmp_path / "out", nav=[{"Home": "index.md"}]))
    assert site.warnings == ["other.md: page exists but is not in nav"]
    assert (tmp_path / "out/other.html").is_file()


def test_cli_build_and_strict(fixture_docs, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no ./mdbake.yml picked up
    runner = CliRunner()
    out = tmp_path / "site"
    result = runner.invoke(main, ["build", "-d", str(fixture_docs), "-o", str(out), "-q"])
    assert result.exit_code == 0, result.output
    assert (out / "index.html").is_file()
    assert (out / "draft.html").is_file()  # no draft middleware configured

    result = runner.invoke(main, ["build", "-d", str(fixture_docs), "-o", str(out), "-q", "--strict"])
    assert result.exit_code == 1
    assert "strict" in result.output


def test_cli_missing_docs_dir(tmp_path):
    result = CliRunner().invoke(main, ["build", "-d", str(tmp_path / "nope"), "-o", str(tmp_path / "s")])
    assert result.exit_code == 1
    assert "docs_dir does not exist" in result.output


def test_clean_refuses_unsafe(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# x")
    result = CliRunner().invoke(main, ["build", "-d", str(docs), "-o", str(tmp_path), "--clean", "-q"])
    assert result.exit_code == 1
    assert "refusing to clean" in result.output
    assert (docs / "index.md").exists()


def test_cli_serve_missing_site_dir(tmp_path):
    result = CliRunner().invoke(main, ["serve", "-o", str(tmp_path / "nope")])
    assert result.exit_code != 0
    assert "Site directory not found" in result.output


def test_cli_watch(fixture_docs, tmp_path, monkeypatch):
    import livereload

    calls = {"watch": []}

    class FakeServer:
        def watch(self, path, func=None, delay=None):
            calls["watch"].append((path, func))

        def serve(self, **kwargs):
            calls["serve"] = kwargs

    monkeypatch.setattr(livereload, "Server", FakeServer)
    monkeypatch.chdir(tmp_path)  # no mdbake.yml here
    site_dir = tmp_path / "site"
    result = CliRunner().invoke(main, ["watch", "-d", str(fixture_docs), "-o", str(site_dir), "--port", "9000"])
    assert result.exit_code == 0, result.output
    assert (site_dir / "index.html").is_file()
    assert calls["serve"]["root"] == str(site_dir) and calls["serve"]["port"] == 9000
    (path, rebuild), = calls["watch"]
    assert path == str(fixture_docs)
    (site_dir / "index.html").unlink()
    rebuild()
    assert (site_dir / "index.html").is_file()
