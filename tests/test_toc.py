from mdbake.markdown import create_markdown, slugify
from mdbake.toc import build_toc


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  Ünïcode  ok ") == "ünïcode--ok"
    assert slugify("snake_case-and-dash") == "snake_case-and-dash"
    assert slugify("!!!") == "section"


def test_build_toc_nesting():
    toc = build_toc([(1, "T", "t"), (2, "A", "a"), (3, "A1", "a1"), (2, "B", "b"), (4, "B1", "b1")])
    assert [e.id for e in toc] == ["t"]
    assert [e.id for e in toc[0].children] == ["a", "b"]
    assert toc[0].children[0].children[0].id == "a1"
    assert toc[0].children[1].children[0].id == "b1"
    assert toc[0].children[0].url == "#a"


def test_build_toc_max_level_and_no_h1():
    toc = build_toc([(2, "A", "a"), (3, "A1", "a1"), (4, "deep", "d"), (2, "B", "b")], max_level=3)
    assert [e.id for e in toc] == ["a", "b"]
    assert [e.id for e in toc[0].children] == ["a1"]
    assert toc[0].children[0].children == []


def test_heading_ids_from_render():
    env = {}
    html = create_markdown().render("# Title\n## Sub *bold* `code`\n## Sub bold code\n", env)
    assert '<h1 id="title">' in html
    assert '<h2 id="sub-bold-code">' in html
    assert '<h2 id="sub-bold-code-1">' in html
    assert env["headings"] == [(1, "Title", "title"), (2, "Sub bold code", "sub-bold-code"),
                               (2, "Sub bold code", "sub-bold-code-1")]


def test_gfm_features():
    html = create_markdown().render("~~x~~ www.example.com\n\n- [x] done\n\n|a|\n|-|\n|1|\n")
    assert "<s>x</s>" in html
    assert 'href="http://www.example.com"' in html
    assert 'type="checkbox"' in html
    assert "<table>" in html


def test_code_highlight_and_unknown_lang():
    md = create_markdown()
    assert '<pre class="highlight"><code class="language-python">' in md.render("```python\nx = 1\n```\n")
    plain = md.render("```nolang\n<b>\n```\n")
    assert "&lt;b&gt;" in plain and 'class="language-nolang"' in plain
