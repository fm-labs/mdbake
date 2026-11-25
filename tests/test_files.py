from mdbake.files import dest_path_for, discover


def test_dest_path_mapping():
    assert dest_path_for("foo.md") == "foo.html"
    assert dest_path_for("foo/bar.md") == "foo/bar.html"
    assert dest_path_for("index.md") == "index.html"
    assert dest_path_for("foo/index.md") == "foo/index.html"
    assert dest_path_for("foo/README.md") == "foo/index.html"
    assert dest_path_for("foo/README.md", dir_has_index_md=True) == "foo/README.html"
    assert dest_path_for("img/logo.png") == "img/logo.png"


def test_discover(fixture_docs):
    files = discover(fixture_docs)
    pages = sorted(f.src_path for f in files.pages())
    assert pages == [
        "draft.md",
        "guide/advanced/tuning.md",
        "guide/index.md",
        "guide/install.md",
        "guide/usage.md",
        "index.md",
    ]
    assert [f.src_path for f in files.assets()] == ["img/logo.svg"]
    assert ".hidden.md" not in files
    assert files.get("guide/index.md").is_index


def test_discover_excludes_site_dir(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "b.md").write_text("# B")
    files = discover(tmp_path, exclude=[tmp_path / "site"])
    assert [f.src_path for f in files] == ["a.md"]


def test_readme_with_index(tmp_path):
    (tmp_path / "index.md").write_text("# I")
    (tmp_path / "README.md").write_text("# R")
    files = discover(tmp_path)
    assert files.get("index.md").dest_path == "index.html"
    assert files.get("README.md").dest_path == "README.html"
