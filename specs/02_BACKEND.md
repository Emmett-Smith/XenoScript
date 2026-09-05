# 02 — Backend: ingest, symbol table, MCP server, sandbox

**Owner: Emmett.** Depends on `01_LANGUAGE.md` only for the CLI contract, so
you can build against a stub verifier immediately — see §6.

---

## 1. Ingest

`ashlar/ingest/`. One command:

```
python -m ashlar.ingest --corpus corpora/plinth
```

Output, printed and written to `corpora/plinth/.index/manifest.json`:

```
PLINTH ingested
  docs      3 files    1,412 chunks
  examples 15 files      847 lines indexed
  pairs    15 tasks
  symbols  52 (source: verifier)
  index    corpora/plinth/.index/  (bm25.pkl, symbols.db, chunks.jsonl)
```

Those counts go on screen in the demo. Make them accurate and make them fast
(target under 10 seconds for PLINTH).

### Chunking

Strategy from `meta.yaml` (`heading` for PLINTH).

- `heading`: split on markdown headings, keep the heading path as metadata.
  Chunks over 1500 chars split on paragraph, retaining heading path.
- Never split mid-code-block.
- Each chunk records `{file, start_line, end_line, heading_path, text, kind}`.

Example files are **not chunked**. They are indexed whole and read by line
range. The agent's most valuable move is "show me a real program that does
this," which needs intact files.

### Index

- **BM25 over chunks and example lines.** `rank_bm25` or a 60-line
  implementation; either is fine. Weight per `meta.yaml` (0.75 for PLINTH).
- **Embeddings optional.** Only if a local embedding model is already
  available offline. If it costs more than an hour, skip it — BM25-only is a
  legitimate ship state and for command languages it is often better. Exact
  keyword match on `bind` beats semantic similarity.
- Tokenizer must preserve identifiers with underscores as single tokens
  (`noise_floor`, `end_platform`). Default word tokenizers split these and it
  wrecks retrieval quality. **Test this specifically.**

## 2. Symbol table

`ashlar/ingest/symbols.py` → `symbols.db` (SQLite).

```sql
CREATE TABLE symbols (
  name           TEXT PRIMARY KEY,
  kind           TEXT NOT NULL,      -- block|attribute|statement|type|unit|keyword
  valid_parents  TEXT,               -- JSON array
  valid_children TEXT,               -- JSON array
  arg_shape      TEXT,
  dimension      TEXT,               -- length|time|speed|angle|frequency|power|null
  required       INTEGER DEFAULT 0,
  range_min      REAL,
  range_max      REAL,
  doc_anchor     TEXT,               -- "docs/manual.md#platform-attributes"
  example_refs   TEXT,               -- JSON [{file,line}]
  source         TEXT NOT NULL       -- verifier|examples|docs
);
CREATE INDEX idx_kind ON symbols(kind);

CREATE TABLE example_index (
  symbol TEXT, file TEXT, line INTEGER, snippet_start INTEGER, snippet_end INTEGER
);

CREATE TABLE failures (
  id INTEGER PRIMARY KEY, code TEXT, message TEXT,
  before_src TEXT, after_src TEXT, resolved INTEGER, ts TEXT
);

CREATE TABLE verified_cache (
  key TEXT PRIMARY KEY,              -- normalized task text hash
  task TEXT, source TEXT, iterations INTEGER, ts TEXT
);
```

### Precedence — this matters

Build the table from three sources in strict priority order:

1. **`verifier.symbols`** if `meta.yaml` defines it. This is ground truth.
   PLINTH provides it. Sets `source='verifier'`.
2. **Parsed examples.** For languages with no symbol dump (COBOL), parse the
   example corpus with a real grammar (`tree-sitter-cobol` or ProLeap ANTLR)
   and derive symbols from actual usage. `source='examples'`.
3. **Doc scraping.** Last resort, lowest trust. `source='docs'`.

Never let a lower tier overwrite a higher one. Do enrich: docs supply
`doc_anchor` for symbols the verifier reported, examples supply
`example_refs`.

**Why this order:** documentation is stale, toolchains are not. A doc-derived
table inherits every error in a 30-year-old manual. This precedence rule is
one of the genuinely defensible ideas in the project — make sure it survives
into the pitch.

## 3. MCP server

`ashlar/mcp/server.py`. stdio transport. Signatures and return shapes are
fixed by `00_ARCHITECTURE.md` §6 — implement exactly, do not improvise.

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("ashlar")

@mcp.tool()
def lookup_symbol(name: str) -> dict:
    """Confirm a symbol exists and where it is legal. Call this before
    emitting any identifier you are not certain about. Returns valid parent
    blocks, argument shape, required units, and real usage locations."""

@mcp.tool()
def grep_corpus(pattern: str, limit: int = 20, kind: str = "all") -> list[dict]:
    """Regex search across documentation and example source. kind is one of
    all|doc|example|cache. Returns file, line, matching text, and surrounding
    context lines."""

@mcp.tool()
def get_examples(symbol: str, n: int = 3) -> list[dict]:
    """Return real, verified usages of a symbol from the example corpus.
    Prefer this over reasoning from documentation alone."""

@mcp.tool()
def read_file(path: str, start: int = 1, end: int = -1) -> dict:
    """Read a line range from a corpus file. Paths are relative to the corpus
    root and are confined to it."""

@mcp.tool()
def verify(source: str, run: bool = False, stdin: str = "") -> dict:
    """Compile or parse candidate source in an offline sandbox, optionally
    executing it. Never return code to the user that has not passed this.
    Returns ok plus a list of errors with line numbers and codes."""

if __name__ == "__main__":
    mcp.run()
```

Notes:

- Docstrings are the entire prompt the model sees for these. Improve wording
  freely; do not shorten to bare descriptions. The imperative phrasing
  measurably raises call rates on weaker models.
- `read_file` must reject path traversal. Resolve and assert the real path is
  under the corpus root. Return `{"error": ...}` otherwise.
- `grep_corpus` on an invalid regex returns `{"error": "invalid pattern: ..."}`
  rather than raising. The model will send bad regexes; handle it.
- No tool ever raises to the model.

**Do not add tools.** Read `00_ARCHITECTURE.md` §7 before you are tempted. The
tools are generic primitives parameterized by argument; coverage scales in the
corpus, not in code.

## 4. Sandbox

`ashlar/mcp/sandbox.py`.

```python
def run_verifier(source: str, mode: str, stdin: str = "") -> dict:
    """mode: 'parse' | 'run'. Returns the §5 verifier result contract."""
```

Implementation:

1. Write `source` to a tmpdir as `candidate<extension>`.
2. Build the command from `meta.yaml`, substituting `{file}`.
3. Run in a container:
   ```
   docker run --rm --network=none --read-only
     --tmpfs /work:rw,size=64m --memory=512m --cpus=1
     --user 65534:65534 -v <tmpdir>:/in:ro
     ashlar/plinth:latest <cmd>
   ```
4. Wall-clock timeout from `meta.yaml`. On timeout, kill and return a
   synthetic `EHARNESS` error — never hang the loop.
5. Parse output. If the toolchain supports `--json`, use it. Otherwise apply a
   per-language regex adapter (COBOL: `cobc` emits
   `file:line: error: message`).
6. Normalize to the contract. Unparseable output → `ok: false` with one
   `EHARNESS` error. **Never silently pass.**

**Fallback for the demo:** if Docker is unavailable or slow on the demo
machine, support `sandbox.mode: subprocess` in `meta.yaml` — same interface,
`subprocess.run` with a timeout and a scratch cwd. Weaker isolation, identical
behavior. Have this working before the event; container startup latency has
ruined more demos than bugs have.

## 5. Failure memory and verified cache

Both live in `symbols.db` (schema §2), written by the harness, read by ingest
and by the MCP server.

- `verified_cache` entries are indexed into BM25 with `kind='cache'`, so
  `grep_corpus` finds them. This is the entire "learning" mechanism: data, not
  weights.
- `failures` supports `SELECT code, COUNT(*) ... GROUP BY code ORDER BY 2 DESC
  LIMIT 5` → injected into the system prompt by the harness.
- Re-derive symbols after each accepted solution so user-defined identifiers
  become known. Cheap; just re-run the examples pass over the cache.

## 6. Build order — unblock yourself immediately

Do not wait for the real interpreter.

1. **Hour 1:** stub verifier. A 20-line script that returns
   `{"ok": true, "errors": []}` unless the source contains the literal string
   `FAIL`, in which case it returns a fabricated E041 at line 3. Register it as
   a `corpora/stub/meta.yaml`. The whole harness and frontend can now be built
   and tested end to end.
2. Ingest + BM25 against `corpora/stub` with a handful of fake docs.
3. Symbol table with the `source` precedence logic, tested against a
   hand-written `symbols --json` fixture.
4. MCP server, all five tools, tested with the MCP inspector before wiring the
   harness.
5. Swap `corpora/stub` for `corpora/plinth` when the interpreter lands. If §1's
   corpus-agnostic invariant held, this is a one-line config change. **That
   swap is also the demo's closing move**, so it needs to work anyway.

## 7. Definition of done

- [ ] `python -m ashlar.ingest --corpus corpora/plinth` under 10s, accurate counts
- [ ] Underscore identifiers tokenize as single BM25 tokens (test asserted)
- [ ] `pairs/*/solution.plth` excluded from index (test asserted)
- [ ] Symbol table: 52 PLINTH symbols, all `source='verifier'`
- [ ] Source precedence tested: doc-scraped entry cannot overwrite verifier entry
- [ ] All five MCP tools respond correctly via MCP inspector
- [ ] `read_file("../../etc/passwd")` → error, not a read
- [ ] Invalid regex to `grep_corpus` → error dict, no exception
- [ ] Sandbox verified with `--network=none`; timeout path returns EHARNESS
- [ ] `sandbox.mode: subprocess` fallback works
- [ ] Zero occurrences of `plinth` or `cobol` under `ashlar/` (grep asserted in CI)
