from ashlar.ingest.chunker import chunk_heading


def test_chunk_heading_basic_sections_and_heading_path():
    text = (
        "# Top\n"
        "intro text\n"
        "## Sub A\n"
        "content a\n"
        "## Sub B\n"
        "content b\n"
    )
    chunks = chunk_heading("manual.md", text)
    assert [c["heading_path"] for c in chunks] == [["Top"], ["Top", "Sub A"], ["Top", "Sub B"]]
    assert chunks[0]["text"].startswith("# Top")
    assert "content a" in chunks[1]["text"]
    assert "content b" in chunks[2]["text"]
    # line ranges are 1-indexed and contiguous
    assert chunks[0]["start_line"] == 1
    assert chunks[1]["start_line"] == 3


def test_chunk_heading_preamble_before_first_heading_kept_with_empty_path():
    text = "preamble line\n\n# First Heading\nbody\n"
    chunks = chunk_heading("doc.md", text)
    assert chunks[0]["heading_path"] == []
    assert "preamble line" in chunks[0]["text"]
    assert chunks[1]["heading_path"] == ["First Heading"]


def test_chunk_heading_no_headings_is_one_chunk():
    text = "just some text\nwith no headings at all\n"
    chunks = chunk_heading("plain.md", text)
    assert len(chunks) == 1
    assert chunks[0]["heading_path"] == []


def test_chunk_heading_splits_over_1500_chars_on_paragraph_boundary():
    para1 = "word " * 400  # ~2000 chars, forces a split
    para2 = "second paragraph text here.\n"
    text = f"# Big Section\n{para1}\n\n{para2}"
    chunks = chunk_heading("big.md", text)
    assert len(chunks) >= 2
    for c in chunks:
        assert c["heading_path"] == ["Big Section"]


def test_chunk_heading_never_splits_mid_code_block():
    # A single fenced code block bigger than MAX_CHUNK_CHARS must stay
    # whole -- never split mid code-block, even though it exceeds the cap.
    code_lines = "\n".join(f"line_{i} = {i}" for i in range(200))
    text = f"# Section\n```\n{code_lines}\n```\n"
    chunks = chunk_heading("code.md", text)
    assert len(chunks) == 1
    assert chunks[0]["text"].count("```") == 2
    assert "line_0 = 0" in chunks[0]["text"]
    assert "line_199 = 199" in chunks[0]["text"]


def test_chunk_heading_deeper_then_shallower_heading_pops_stack_correctly():
    text = (
        "# A\n"
        "## A1\n"
        "text1\n"
        "### A1a\n"
        "text1a\n"
        "## A2\n"
        "text2\n"
    )
    chunks = chunk_heading("nest.md", text)
    paths = [c["heading_path"] for c in chunks]
    assert paths == [["A"], ["A", "A1"], ["A", "A1", "A1a"], ["A", "A2"]]
