from ashlar.harness.tool_client import FakeToolClient, ToolClient


def test_fake_tool_client_satisfies_protocol():
    client = FakeToolClient()
    assert isinstance(client, ToolClient)


def test_lookup_symbol_found_and_not_found():
    client = FakeToolClient(symbols={"altitude": {"found": True, "name": "altitude", "kind": "attribute"}})
    assert client.lookup_symbol("altitude")["found"] is True
    assert client.lookup_symbol("nonexistent")["found"] is False


def test_grep_corpus_invalid_regex_returns_error_dict_not_exception():
    client = FakeToolClient()
    result = client.grep_corpus("(unclosed[")
    assert isinstance(result, list)
    assert "error" in result[0]


def test_grep_corpus_matches_by_pattern_substring():
    client = FakeToolClient(grep_hits={"inherit": [{"file": "a.plth", "line": 1, "text": "inherit from x"}]})
    hits = client.grep_corpus("inherit|bind")
    assert hits and hits[0]["file"] == "a.plth"


def test_get_examples_respects_n():
    client = FakeToolClient(examples={"bind": [{"file": "a", "start": 1, "end": 2}, {"file": "b", "start": 3, "end": 4}]})
    assert len(client.get_examples("bind", n=1)) == 1


def test_read_file_rejects_path_traversal():
    client = FakeToolClient(read_files={"docs/manual.md": "line1\nline2\n"})
    result = client.read_file("../../etc/passwd")
    assert "error" in result


def test_read_file_returns_line_range():
    client = FakeToolClient(read_files={"docs/manual.md": "l1\nl2\nl3\nl4\n"})
    result = client.read_file("docs/manual.md", 2, 3)
    assert result["text"] == "l2\nl3"


def test_verify_default_contract_matches_stub_verifier_behavior():
    client = FakeToolClient()
    assert client.verify("clean source")["ok"] is True
    bad = client.verify("has FAIL in it")
    assert bad["ok"] is False
    assert bad["errors"][0]["code"] == "E041"
    assert bad["errors"][0]["line"] == 3


def test_all_calls_are_recorded():
    client = FakeToolClient()
    client.lookup_symbol("x")
    client.verify("ok")
    assert client.calls[0][0] == "lookup_symbol"
    assert client.calls[1][0] == "verify"
