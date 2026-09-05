"""The model layer. One real class, one fake, same call shape.

Per 00_ARCHITECTURE.md #10 / #2 (process topology): everything speaks
OpenAI-compatible /v1/chat/completions. Ollama for laptop/demo, vLLM for real
GPU deployment. The model name is never hardcoded here -- it comes from
`Config.model.name`, which comes from `config.yaml` only.

`FakeModel` is not a fallback path, it is a permanent testing seam. Every
loop test runs against it with zero network access; the eval runner will use
it too for offline arms.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from ashlar.config import ModelConfig

OnToken = Callable[[str], None]


class ModelClient(Protocol):
    """The interface `loop.py` depends on. `Model` and `FakeModel` both
    satisfy it; nothing in the loop may import `openai` directly."""

    name: str

    def generate(
        self,
        system: str,
        context: str,
        prompt: str,
        history: str,
        *,
        tools: list[dict] | None = None,
        stream: bool = True,
        on_token: OnToken | None = None,
    ) -> str:
        ...


def _build_user_message(context: str, prompt: str, history: str) -> str:
    parts = []
    if context:
        parts.append(context.strip())
    if history:
        parts.append(history.strip())
    parts.append(f"Task:\n{prompt.strip()}")
    return "\n\n".join(p for p in parts if p)


class Model:
    """OpenAI-compatible chat client. Talks to whatever `cfg.base_url` names
    (Ollama at localhost:11434/v1 tonight; vLLM in real deployment)."""

    def __init__(self, cfg: ModelConfig):
        # Imported lazily so FakeModel-only test runs never need the openai
        # package's transport machinery to be importable/network-capable.
        from openai import OpenAI

        self.client = OpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key or "none",
            timeout=cfg.request_timeout_s,
        )
        self.name = cfg.name
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens

    def generate(
        self,
        system: str,
        context: str,
        prompt: str,
        history: str,
        *,
        tools: list[dict] | None = None,
        stream: bool = True,
        on_token: OnToken | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": _build_user_message(context, prompt, history)},
        ]
        kwargs: dict = {
            "model": self.name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        if not stream:
            resp = self.client.chat.completions.create(stream=False, **kwargs)
            return resp.choices[0].message.content or ""

        chunks: list[str] = []
        resp = self.client.chat.completions.create(stream=True, **kwargs)
        for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
                if on_token:
                    on_token(delta)
        return "".join(chunks)


@dataclass
class FakeModel:
    """Deterministic, network-free stand-in for `Model`.

    Scripted by call count: `responses[i]` is returned on the i-th call to
    `generate` (0-indexed). If there are more calls than responses, the last
    response repeats. This is how we script "fails iteration 1, succeeds
    iteration 2" without touching a network.

    `responses` can hold literal source strings, or use
    `FakeModel.from_fixtures` to load them from files under
    `ashlar/harness/fixtures/` (handy when a canned source is long/multi-line
    and awkward to inline in a test).
    """

    responses: list[str] = field(default_factory=list)
    name: str = "fake-model"
    calls: list[dict] = field(default_factory=list, repr=False)

    @classmethod
    def from_fixtures(cls, fixture_dir, filenames: Iterable[str], name: str = "fake-model") -> FakeModel:
        from pathlib import Path

        base = Path(fixture_dir)
        responses = [(base / fn).read_text() for fn in filenames]
        return cls(responses=responses, name=name)

    def generate(
        self,
        system: str,
        context: str,
        prompt: str,
        history: str,
        *,
        tools: list[dict] | None = None,
        stream: bool = True,
        on_token: OnToken | None = None,
    ) -> str:
        idx = len(self.calls)
        self.calls.append({
            "system": system,
            "context": context,
            "prompt": prompt,
            "history": history,
        })
        if not self.responses:
            source = ""
        else:
            source = self.responses[min(idx, len(self.responses) - 1)]
        if stream and on_token:
            for tok in _fake_tokenize(source):
                on_token(tok)
        return source


def _fake_tokenize(source: str) -> list[str]:
    """Splits canned source into whitespace-preserving chunks so FakeModel
    can still drive `model_token` events for UI/event-sequence tests.
    `"".join(_fake_tokenize(s)) == s` always holds."""
    if not source:
        return []
    words = source.split(" ")
    tokens = [w + " " for w in words[:-1]]
    tokens.append(words[-1])
    return tokens
