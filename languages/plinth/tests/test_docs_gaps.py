"""01_LANGUAGE.md Sec 8/9: inherit and every/for must never appear in the
docs, only in examples; plinth symbols must still report them (the
deliberate asymmetry the whole demo moment rests on)."""
from pathlib import Path

import re

import symbols as S

ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = ROOT / "corpora" / "plinth" / "docs"
EXAMPLES_DIR = ROOT / "corpora" / "plinth" / "examples"

_INHERIT_RE = re.compile(r"\binherit\b")
_EVERY_KEYWORD_RE = re.compile(r"\bevery\s+[\d.]+")  # the grammar usage, not the English word


def test_inherit_absent_from_docs():
    for doc in DOCS_DIR.glob("*.md"):
        text = doc.read_text()
        assert not _INHERIT_RE.search(text), f"'inherit' leaked into {doc.name}"


def test_every_for_grammar_absent_from_docs():
    for doc in DOCS_DIR.glob("*.md"):
        text = doc.read_text()
        assert not _EVERY_KEYWORD_RE.search(text), f"'every <time>' leaked into {doc.name}"


def test_inherit_present_in_examples():
    found = any("inherit from" in p.read_text() for p in EXAMPLES_DIR.glob("*.plth"))
    assert found, "no example demonstrates 'inherit from'"


def test_every_for_present_in_examples():
    found = any(_EVERY_KEYWORD_RE.search(p.read_text()) for p in EXAMPLES_DIR.glob("*.plth"))
    assert found, "no example demonstrates 'every ... for'"


def test_symbols_reports_both_examples_only_features():
    names = {s["name"] for s in S.build_symbol_table()}
    assert "inherit" in names
    assert "every" in names
    assert "for" in names
