from ashlar.harness.memory import Memory, cache_key, normalize_task
from ashlar.harness.repair import HistoryTurn


def test_normalize_task_collapses_whitespace_case_and_punctuation():
    a = normalize_task("  Define a Platform!  With   altitude.  ")
    b = normalize_task("define a platform with altitude")
    assert a == b


def test_cache_key_stable_for_equivalent_text():
    assert cache_key("Define a platform.") == cache_key("define a PLATFORM")


def test_record_success_then_exact_cache_hit(tmp_path):
    mem = Memory(tmp_path / "symbols.db")
    mem.record_success("define a platform with altitude 2000m", "define platform p1\nend platform\n", 2)
    hit = mem.cache_lookup("define a platform with altitude 2000m")
    assert hit is not None
    assert hit.source == "define platform p1\nend platform\n"
    assert hit.iterations == 2


def test_cache_lookup_misses_on_unrelated_prompt(tmp_path):
    mem = Memory(tmp_path / "symbols.db")
    mem.record_success("define a platform", "src", 1)
    assert mem.cache_lookup("completely unrelated task about waypoints and sensors") is None


def test_near_match_hits_above_similarity_floor(tmp_path):
    mem = Memory(tmp_path / "symbols.db")
    mem.record_success("define a platform with altitude 2000 meters", "SRC", 1)
    # near-duplicate phrasing, not an exact hash match
    hit = mem.cache_lookup("define a platform with altitude 2000 meter")
    assert hit is not None
    assert hit.source == "SRC"


def test_record_failure_and_top_failures(tmp_path):
    mem = Memory(tmp_path / "symbols.db")
    history = [
        HistoryTurn(1, "src1", [{"code": "E041", "message": "m"}], "attempt 1: E041 at line 3", "detail1"),
        HistoryTurn(2, "src2", [{"code": "E041", "message": "m"}, {"code": "E020", "message": "m2"}],
                    "attempt 2: E041 at line 3", "detail2"),
    ]
    mem.record_failure("some task", history)
    top = mem.top_failures(5)
    assert top[0].startswith("E041 (2x")


def test_top_failures_empty_when_no_history(tmp_path):
    mem = Memory(tmp_path / "symbols.db")
    assert mem.top_failures(5) == []


def test_schema_matches_backend_spec_table_names(tmp_path):
    mem = Memory(tmp_path / "symbols.db")
    import sqlite3

    con = sqlite3.connect(mem.db_path)
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert {"symbols", "example_index", "failures", "verified_cache"} <= tables
