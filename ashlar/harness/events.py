"""Event emission matching 00_ARCHITECTURE.md #8, verbatim.

The harness never hands raw dicts to callers by hand-rolling them inline --
every event shape is built here so the field names in the contract cannot
drift. `ts` is milliseconds since task_start, computed from a monotonic clock
captured at construction time.

Adding fields to an event is fine. Renaming an existing field, or emitting an
event type not in the contract, is not -- that breaks the frontend reducer.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

EmitFn = Callable[[dict[str, Any]], None]


class EventEmitter:
    """Wraps a raw `emit(dict)` callable and stamps every event with `ts`."""

    def __init__(self, task_id: str, emit: EmitFn):
        self.task_id = task_id
        self._emit = emit
        self._t0 = time.monotonic()

    def _ts(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    def _send(self, payload: dict[str, Any]) -> None:
        payload["ts"] = self._ts()
        self._emit(payload)

    def task_start(self, prompt: str) -> None:
        self._send({"type": "task_start", "task_id": self.task_id, "prompt": prompt})

    def tool_call(self, tool: str, args: dict[str, Any]) -> None:
        self._send({"type": "tool_call", "tool": tool, "args": args})

    def tool_result(self, tool: str, hits: int, preview: list[Any]) -> None:
        self._send({"type": "tool_result", "tool": tool, "hits": hits, "preview": preview})

    def model_start(self, iteration: int) -> None:
        self._send({"type": "model_start", "iteration": iteration})

    def model_token(self, text: str) -> None:
        self._send({"type": "model_token", "text": text})

    def model_done(self, iteration: int, source: str) -> None:
        self._send({"type": "model_done", "iteration": iteration, "source": source})

    def verify_start(self, iteration: int) -> None:
        self._send({"type": "verify_start", "iteration": iteration})

    def verify_result(self, iteration: int, vr: dict[str, Any]) -> None:
        self._send({
            "type": "verify_result",
            "iteration": iteration,
            "ok": vr.get("ok", False),
            "errors": vr.get("errors", []),
        })

    def repair_start(self, iteration: int, fixing: list[str]) -> None:
        self._send({"type": "repair_start", "iteration": iteration, "fixing": fixing})

    def cache_hit(self, key: str) -> None:
        self._send({"type": "cache_hit", "key": key})

    def task_done(self, ok: bool, iterations: int, source: str, citations: list[Any]) -> None:
        self._send({
            "type": "task_done",
            "task_id": self.task_id,
            "ok": ok,
            "iterations": iterations,
            "source": source,
            "citations": citations,
        })

    def task_failed(self, reason: str, last_errors: list[Any]) -> None:
        self._send({
            "type": "task_failed",
            "task_id": self.task_id,
            "reason": reason,
            "last_errors": last_errors,
        })
