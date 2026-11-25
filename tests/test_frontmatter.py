import pytest

from mdbake.frontmatter import FrontmatterError, split_frontmatter


def test_no_frontmatter():
    assert split_frontmatter("# Hi\n") == ({}, "# Hi\n")


def test_frontmatter():
    meta, body = split_frontmatter("---\ntitle: X\ntags: [a, b]\n---\n# Body\n")
    assert meta == {"title": "X", "tags": ["a", "b"]}
    assert body == "# Body\n"


def test_empty_frontmatter_and_bom():
    assert split_frontmatter("﻿---\n---\ntext") == ({}, "text")


def test_dots_terminator():
    assert split_frontmatter("---\na: 1\n...\nbody") == ({"a": 1}, "body")


def test_thematic_break_not_frontmatter():
    text = "Intro\n\n---\n\nMore"
    assert split_frontmatter(text) == ({}, text)


@pytest.mark.parametrize("text", ["---\n- a\n- b\n---\n", "---\na: [\n---\n"])
def test_invalid(text):
    with pytest.raises(FrontmatterError):
        split_frontmatter(text)
