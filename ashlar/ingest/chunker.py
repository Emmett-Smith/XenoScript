"""Doc chunking.

Strategy is selected purely by the string in ``meta.yaml``'s
``retrieval.chunk_strategy`` (``heading`` | ``fixed`` | ``blank_line``) --
this module must never branch on a language or corpus name.

Example files are handled separately by the ingest pipeline: they are
indexed whole and read by line range, never chunked (see
specs/02_BACKEND.md #1). Nothing here touches example files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHUNK_CHARS = 1500

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^\s*```")


@dataclass
class Chunk:
    file: str
    start_line: int
    end_line: int
    heading_path: list[str]
    text: str
    kind: str = "doc"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "file": self.file,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "heading_path": list(self.heading_path),
            "text": self.text,
        }


def _split_on_paragraphs_respecting_fences(lines: list[str]) -> list[tuple[int, int]]:
    """0-based inclusive (start, end) paragraph ranges over ``lines``. A
    fenced ```code block``` is one atomic paragraph and is never split, even
    across the blank lines that might appear inside it."""
    ranges: list[tuple[int, int]] = []
    n = len(lines)
    para_start: int | None = None
    in_fence = False
    for i in range(n):
        line = lines[i]
        if FENCE_RE.match(line):
            if para_start is None:
                para_start = i
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.strip() == "":
            if para_start is not None:
                ranges.append((para_start, i - 1))
                para_start = None
        else:
            if para_start is None:
                para_start = i
    if para_start is not None:
        ranges.append((para_start, n - 1))
    return ranges


def _pack_paragraphs(
    lines: list[str], para_ranges: list[tuple[int, int]], max_chars: int
) -> list[tuple[int, int]]:
    """Greedily merge adjacent paragraphs into sub-chunks under
    ``max_chars``. A single paragraph bigger than ``max_chars`` (e.g. one
    large fenced code block) is kept whole -- never split mid code-block."""
    packed: list[tuple[int, int]] = []
    cur_start: int | None = None
    cur_end: int | None = None
    cur_len = 0
    for s, e in para_ranges:
        para_len = len("\n".join(lines[s : e + 1])) + 1
        if cur_start is None:
            cur_start, cur_end, cur_len = s, e, para_len
        elif cur_len + para_len <= max_chars:
            cur_end = e
            cur_len += para_len
        else:
            packed.append((cur_start, cur_end))
            cur_start, cur_end, cur_len = s, e, para_len
    if cur_start is not None:
        packed.append((cur_start, cur_end))
    return packed


def chunk_heading(file_label: str, text: str) -> list[dict]:
    """Split markdown ``text`` on headings (any level), keeping the full
    heading path (list of ancestor titles) as metadata on each chunk.
    Chunks over ``MAX_CHUNK_CHARS`` are further split on paragraph
    boundaries, retaining the heading path, never splitting mid code-block.
    """
    lines = text.splitlines()
    n = len(lines)

    sections: list[tuple[list[str], int, int]] = []
    stack: list[tuple[int, str]] = []
    cur_start = 0
    cur_path: list[str] = []

    def flush(end_idx: int) -> None:
        if end_idx >= cur_start:
            sections.append((list(cur_path), cur_start, end_idx))

    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            flush(i - 1)
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            cur_path = [t for _, t in stack]
            cur_start = i
    flush(n - 1)

    chunks: list[dict] = []
    for heading_path, s, e in sections:
        sec_lines = lines[s : e + 1]
        sec_text = "\n".join(sec_lines)
        if len(sec_text) <= MAX_CHUNK_CHARS:
            chunks.append(Chunk(file_label, s + 1, e + 1, heading_path, sec_text).to_dict())
            continue
        para_ranges = _split_on_paragraphs_respecting_fences(sec_lines)
        for ps, pe in _pack_paragraphs(sec_lines, para_ranges, MAX_CHUNK_CHARS):
            sub_text = "\n".join(sec_lines[ps : pe + 1])
            chunks.append(
                Chunk(file_label, s + ps + 1, s + pe + 1, heading_path, sub_text).to_dict()
            )
    return chunks


def chunk_fixed(file_label: str, text: str, size: int = MAX_CHUNK_CHARS) -> list[dict]:
    """Simple fixed-size line accumulation. No heading metadata."""
    lines = text.splitlines()
    chunks: list[dict] = []
    cur: list[str] = []
    cur_len = 0
    start = 0
    for i, line in enumerate(lines):
        if cur and cur_len + len(line) + 1 > size:
            chunks.append(Chunk(file_label, start + 1, i, [], "\n".join(cur)).to_dict())
            cur, cur_len, start = [], 0, i
        cur.append(line)
        cur_len += len(line) + 1
    if cur:
        chunks.append(Chunk(file_label, start + 1, len(lines), [], "\n".join(cur)).to_dict())
    return chunks


def chunk_blank_line(file_label: str, text: str) -> list[dict]:
    """Paragraph-boundary chunking with no heading metadata, packed under
    MAX_CHUNK_CHARS, never splitting mid code-block."""
    lines = text.splitlines()
    para_ranges = _split_on_paragraphs_respecting_fences(lines)
    packed = _pack_paragraphs(lines, para_ranges, MAX_CHUNK_CHARS)
    return [
        Chunk(file_label, s + 1, e + 1, [], "\n".join(lines[s : e + 1])).to_dict()
        for s, e in packed
    ]


STRATEGIES = {
    "heading": chunk_heading,
    "fixed": chunk_fixed,
    "blank_line": chunk_blank_line,
}


def chunk_text(strategy: str, file_label: str, text: str) -> list[dict]:
    fn = STRATEGIES.get(strategy, chunk_heading)
    return fn(file_label, text)


def chunk_doc_file(path: Path, file_label: str, strategy: str = "heading") -> list[dict]:
    return chunk_text(strategy, file_label, path.read_text())
