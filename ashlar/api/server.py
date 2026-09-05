"""FastAPI server for the frontend. 03_HARNESS.md #5.

Bind 127.0.0.1 only (see `__main__` below). CORS allowed for the local
frontend origin only (Vite's default dev port, 5173).

Phase-2 integration point: `_build_tool_client` is the one function the
lead agent needs to change to wire the real MCP client once
`ashlar/mcp/server.py` exists (built concurrently in another worktree
tonight, not importable here). It must keep returning something satisfying
`ashlar.harness.tool_client.ToolClient` -- everything else in this file is
unaffected by that swap.

Tonight, with no live model on the configured Ollama endpoint
(`curl localhost:11434/api/tags` returned `{"models": []}` at session
start, re-probed with the same empty result before writing this file), and
no real MCP server buildable in this worktree, `_build_tool_client` uses the
subprocess fallback (`ashlar.harness.subprocess_verify`) for `verify()`
against whichever corpus is active -- real for `corpora/stub`, and it will
work unmodified for any other corpus once one exists, since the fallback
only reads `meta.yaml`. `lookup_symbol`/`grep_corpus`/`get_examples`
have no real backing data yet (backend's ingest isn't built here) and
return empty results honestly rather than fabricating anything.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ashlar.config import REPO_ROOT, Config, CorpusMeta, load_config, load_corpus_meta
from ashlar.harness.loop import Corpus, HarnessDeps, run_task
from ashlar.harness.memory import Memory
from ashlar.harness.model import FakeModel, ModelClient
from ashlar.harness.tool_client import ToolClient
from ashlar.ingest.pipeline import run_ingest
from ashlar.mcp import server as mcp_server
from ashlar.mcp.client import RealToolClient

FRONTEND_ORIGIN = "http://localhost:5173"
CORPORA_DIR = REPO_ROOT / "corpora"
EVAL_REPORTS_DIR = REPO_ROOT / "eval" / "reports"


def _build_model(cfg: Config) -> ModelClient:
    """Real `Model` once a model name is configured; `FakeModel` otherwise.
    Never hardcodes a model name -- reads `cfg.model.name` only."""
    if not cfg.model.name or cfg.model.name == "PENDING_BAKEOFF":
        return FakeModel(responses=[])
    from ashlar.harness.model import Model

    return Model(cfg.model)


def _build_tool_client(meta: CorpusMeta) -> ToolClient:
    """The real `ashlar.mcp.server` tool functions, re-pointed at `meta`'s
    corpus in place -- this is what makes `POST /corpus/switch` change what
    every tool returns without a process restart (03_HARNESS.md #5)."""
    mcp_server.set_active_corpus(meta.root.name)
    return RealToolClient()


def _db_path_for(meta: CorpusMeta) -> Path:
    idx = meta.root / ".index"
    idx.mkdir(parents=True, exist_ok=True)
    return idx / "symbols.db"


def _manifest_for(name: str, meta: CorpusMeta) -> dict[str, Any]:
    root = meta.root
    examples = len(list((root / "examples").glob("*"))) if (root / "examples").is_dir() else 0
    pairs = len(list((root / "pairs").glob("*"))) if (root / "pairs").is_dir() else 0
    # Symbol count is honestly 0 until the backend's ingest builds symbols.db
    # for this corpus -- no fabricated numbers on screen.
    db_path = _db_path_for(meta)
    symbols = 0
    if db_path.exists():
        import sqlite3

        con = sqlite3.connect(db_path)
        try:
            symbols = con.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        except sqlite3.OperationalError:
            symbols = 0
        finally:
            con.close()
    return {
        "name": name,
        "display_name": meta.display_name,
        "symbols": symbols,
        "examples": examples,
        "pairs": pairs,
    }


class _TaskState:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.done = False
        self.lock = threading.Lock()

    def append(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.events.append(event)
            if event["type"] in ("task_done", "task_failed"):
                self.done = True

    def snapshot(self, start: int) -> tuple[list[dict[str, Any]], bool]:
        with self.lock:
            return list(self.events[start:]), self.done


class AppState:
    """Mutable singleton so `POST /corpus/switch` can re-point everything
    live, without a process restart."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.tasks: dict[str, _TaskState] = {}
        self._lock = threading.Lock()
        self.switch_corpus(cfg.corpus)

    def switch_corpus(self, name: str) -> dict[str, Any]:
        available = list_corpora()
        if name not in {c["name"] for c in available}:
            raise HTTPException(status_code=404, detail=f"unknown corpus: {name}")
        with self._lock:
            self.corpus_name = name
            self.meta = load_corpus_meta(name)
            self.memory = Memory(_db_path_for(self.meta))
            self.model = _build_model(self.cfg)
            self.tool_client = _build_tool_client(self.meta)
            self.corpus = Corpus.from_disk(self.meta)
        return _manifest_for(name, self.meta)

    def deps(self) -> HarnessDeps:
        return HarnessDeps(
            model=self.model,
            tool_client=self.tool_client,
            memory=self.memory,
            max_iter=self.cfg.harness.max_iter,
            task_budget_s=self.cfg.harness.task_budget_s,
        )


def list_corpora() -> list[dict[str, Any]]:
    out = []
    if not CORPORA_DIR.is_dir():
        return out
    for entry in sorted(CORPORA_DIR.iterdir()):
        if (entry / "meta.yaml").exists():
            meta = load_corpus_meta(entry.name)
            out.append(_manifest_for(entry.name, meta))
    return out


app = FastAPI(title="ashlar")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

state = AppState(load_config())


class TaskRequest(BaseModel):
    prompt: str
    corpus: str


class CorpusSwitchRequest(BaseModel):
    name: str


@app.post("/task")
def post_task(req: TaskRequest) -> dict[str, str]:
    if req.corpus != state.corpus_name:
        state.switch_corpus(req.corpus)

    task_id = f"t_{uuid.uuid4().hex[:8]}"
    task_state = _TaskState()
    state.tasks[task_id] = task_state
    corpus = state.corpus
    deps = state.deps()

    def _run() -> None:
        run_task(req.prompt, corpus, task_state.append, deps, task_id=task_id)

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task_id}


@app.get("/stream/{task_id}")
def get_stream(task_id: str) -> EventSourceResponse:
    if task_id not in state.tasks:
        raise HTTPException(status_code=404, detail="unknown task_id")
    task_state = state.tasks[task_id]

    async def event_generator():
        sent = 0
        while True:
            events, done = task_state.snapshot(sent)
            for e in events:
                yield {"event": e["type"], "data": json.dumps(e)}
            sent += len(events)
            if done:
                return
            await asyncio.sleep(0.02)

    return EventSourceResponse(event_generator())


@app.get("/corpora")
def get_corpora() -> list[dict[str, Any]]:
    return list_corpora()


@app.post("/corpus/switch")
def post_corpus_switch(req: CorpusSwitchRequest) -> dict[str, Any]:
    return state.switch_corpus(req.name)


# ---------------------------------------------------------------------------
# POST /corpus/create -- onboard a brand new corpus through the UI.
#
# The one hard constraint (see the task brief this endpoint was written
# against): uploaded docs/examples alone can never make `verify()` mean
# anything. This endpoint therefore *requires* the caller to supply real
# verifier commands for a toolchain that already exists on this machine --
# exactly the `meta.yaml` `verifier` block shape from
# 00_ARCHITECTURE.md #4 -- and only treats docs/examples as the retrieval-
# seeding half of onboarding. It never auto-detects or guesses a toolchain;
# it only ever runs the commands the caller explicitly typed, substituted
# into a subprocess the same way every other corpus's verifier already runs
# (`ashlar/mcp/sandbox.py`, unmodified by this endpoint).
# ---------------------------------------------------------------------------

_CORPUS_NAME_RE = re.compile(r"^[a-z0-9_-]+$")
_VALID_OUTPUT_FORMATS = ("json", "text")
_VALID_CHUNK_STRATEGIES = ("heading", "fixed", "blank_line")


class _CorpusCreateError(Exception):
    """Any validation failure in POST /corpus/create. Caught at the route
    boundary and turned into a 4xx `{"error": ...}` body -- never a raw
    500/stack trace to the client, and always raised *before* anything is
    written to disk so a rejected request leaves zero trace under
    `corpora/`."""


def _validate_corpus_name(name: str) -> str:
    name = (name or "").strip()
    if not name or not _CORPUS_NAME_RE.match(name) or len(name) > 64:
        raise _CorpusCreateError(
            "name must be lowercase alphanumeric plus underscore/hyphen only "
            "(no '/', no '..', no spaces) -- got " + repr(name)
        )
    # Defense in depth, same suspicion ashlar/mcp/server.py's read_file
    # traversal check applies to a path argument: confirm the resolved
    # target still lands inside corpora/ before anything is written, even
    # though the regex above should already make escaping impossible.
    target = (CORPORA_DIR / name).resolve()
    try:
        target.relative_to(CORPORA_DIR.resolve())
    except ValueError:
        raise _CorpusCreateError(f"name {name!r} escapes the corpora/ directory")
    return name


def _parse_cmd_field(raw: str | None, field: str, *, required: bool) -> list[str] | None:
    if raw is None or raw.strip() == "":
        if required:
            raise _CorpusCreateError(f"{field} is required")
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _CorpusCreateError(f"{field} is not valid JSON: {exc}")
    if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
        raise _CorpusCreateError(f"{field} must be a JSON array of one or more strings")
    return value


def _sanitized_upload_name(filename: str | None, fallback: str) -> str:
    # Path(...).name strips any directory component (including "..") from
    # an uploaded filename, so a crafted multipart filename can't write
    # outside corpora/<name>/docs|examples/.
    name = Path(filename or "").name
    return name or fallback


@app.post("/corpus/create")
async def post_corpus_create(
    name: str = Form(...),
    display_name: str = Form(...),
    extension: str = Form(...),
    comment_prefix: str = Form("#"),
    parse_cmd: str = Form(...),
    run_cmd: str = Form(...),
    symbols_cmd: str | None = Form(None),
    output_format: str = Form("json"),
    error_regex: str | None = Form(None),
    timeout_s: int = Form(10),
    bm25_weight: float = Form(0.75),
    embedding_weight: float = Form(0.25),
    chunk_strategy: str = Form("heading"),
    docs: list[UploadFile] | None = File(default=None),  # noqa: B008 -- standard FastAPI pattern
    examples: list[UploadFile] | None = File(default=None),  # noqa: B008
) -> JSONResponse:
    docs = docs or []
    examples = examples or []
    try:
        clean_name = _validate_corpus_name(name)
        target_dir = CORPORA_DIR / clean_name
        if target_dir.exists():
            raise _CorpusCreateError(f"corpus {clean_name!r} already exists")

        clean_display_name = (display_name or "").strip()
        if not clean_display_name:
            raise _CorpusCreateError("display_name is required")

        clean_extension = (extension or "").strip()
        if not clean_extension.startswith("."):
            raise _CorpusCreateError("extension must start with '.' e.g. '.foo'")

        clean_comment_prefix = comment_prefix if comment_prefix else "#"

        parse_list = _parse_cmd_field(parse_cmd, "parse_cmd", required=True)
        run_list = _parse_cmd_field(run_cmd, "run_cmd", required=True)
        symbols_list = _parse_cmd_field(symbols_cmd, "symbols_cmd", required=False)

        if output_format not in _VALID_OUTPUT_FORMATS:
            raise _CorpusCreateError(f"output_format must be one of {_VALID_OUTPUT_FORMATS}")
        clean_error_regex: str | None = None
        if output_format == "text":
            # Same defensive validation ashlar/mcp/sandbox.py's run_verifier
            # already performs on this exact field -- consistent rejection
            # shape, checked here instead of at first-verify time.
            if not error_regex or not error_regex.strip():
                raise _CorpusCreateError(
                    "error_regex is required when output_format is 'text'"
                )
            try:
                re.compile(error_regex)
            except re.error as exc:
                raise _CorpusCreateError(f"error_regex is not a valid regex: {exc}")
            clean_error_regex = error_regex

        if timeout_s <= 0:
            raise _CorpusCreateError("timeout_s must be a positive integer")
        if bm25_weight < 0 or embedding_weight < 0:
            raise _CorpusCreateError("bm25_weight and embedding_weight must be >= 0")
        if chunk_strategy not in _VALID_CHUNK_STRATEGIES:
            raise _CorpusCreateError(f"chunk_strategy must be one of {_VALID_CHUNK_STRATEGIES}")

        # Read every upload's bytes now, before any write to disk, so a
        # failure partway through reading never leaves a half-written
        # corpus directory behind.
        doc_uploads = [
            (_sanitized_upload_name(f.filename, f"doc_{i}"), await f.read())
            for i, f in enumerate(docs)
            if f.filename
        ]
        example_uploads = [
            (_sanitized_upload_name(f.filename, f"example_{i}"), await f.read())
            for i, f in enumerate(examples)
            if f.filename
        ]
    except _CorpusCreateError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    # --- Validation is complete. Nothing below this line may reject the
    # request; everything from here on either succeeds or rolls back. ---

    warnings: list[str] = []
    if not doc_uploads and not example_uploads:
        warnings.append(
            "no docs or examples uploaded -- verification against the real "
            "toolchain will still work, but retrieval has nothing to search "
            "yet and will perform badly until some are added"
        )

    meta_dict: dict[str, Any] = {
        "language": clean_name,
        "display_name": clean_display_name,
        "extension": clean_extension,
        "comment_prefix": clean_comment_prefix,
        "verifier": {"parse": parse_list, "run": run_list},
        "sandbox": {"mode": "subprocess", "timeout_s": timeout_s, "memory_mb": 512},
        "retrieval": {
            "bm25_weight": bm25_weight,
            "embedding_weight": embedding_weight,
            "chunk_strategy": chunk_strategy,
        },
    }
    if symbols_list:
        meta_dict["verifier"]["symbols"] = symbols_list
    if output_format != "json":
        meta_dict["verifier"]["output_format"] = output_format
    if clean_error_regex:
        meta_dict["verifier"]["error_regex"] = clean_error_regex

    created = False
    try:
        target_dir.mkdir(parents=True, exist_ok=False)
        created = True
        (target_dir / "docs").mkdir()
        (target_dir / "examples").mkdir()
        for fname, content in doc_uploads:
            (target_dir / "docs" / fname).write_bytes(content)
        for fname, content in example_uploads:
            (target_dir / "examples" / fname).write_bytes(content)
        (target_dir / "meta.yaml").write_text(yaml.safe_dump(meta_dict, sort_keys=False))

        run_ingest(clean_name)
        result = _manifest_for(clean_name, load_corpus_meta(clean_name))
    except Exception as exc:
        if created:
            shutil.rmtree(target_dir, ignore_errors=True)
        return JSONResponse(
            status_code=400, content={"error": f"failed to create corpus: {exc}"}
        )

    result["warnings"] = warnings
    return JSONResponse(status_code=200, content=result)


@app.get("/eval/latest")
def get_eval_latest() -> dict[str, Any]:
    if not EVAL_REPORTS_DIR.is_dir():
        return {"error": "no report yet"}
    reports = sorted(EVAL_REPORTS_DIR.glob("*.json"))
    if not reports:
        return {"error": "no report yet"}
    return json.loads(reports[-1].read_text())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=state.cfg.api.host, port=state.cfg.api.port)
