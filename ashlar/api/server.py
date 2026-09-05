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
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ashlar.config import REPO_ROOT, Config, CorpusMeta, load_config, load_corpus_meta
from ashlar.harness.loop import Corpus, HarnessDeps, run_task
from ashlar.harness.memory import Memory
from ashlar.harness.model import FakeModel, ModelClient
from ashlar.harness.tool_client import ToolClient
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
