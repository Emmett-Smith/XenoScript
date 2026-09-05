"""Load config.yaml and corpora/<name>/meta.yaml.

This module is the only place that knows the shape of those two files. It
carries no logic specific to any single language or corpus -- see
00_ARCHITECTURE.md #3's invariant.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclasses.dataclass
class ModelConfig:
    base_url: str
    name: str
    api_key: str
    temperature: float
    max_tokens: int
    request_timeout_s: int = 120


@dataclasses.dataclass
class HarnessConfig:
    max_iter: int = 4
    task_budget_s: int = 300


@dataclasses.dataclass
class SandboxConfig:
    mode: str = "subprocess"  # "subprocess" | "container" (container: NotImplementedError tonight)


@dataclasses.dataclass
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclasses.dataclass
class Config:
    corpus: str
    model: ModelConfig
    harness: HarnessConfig
    sandbox: SandboxConfig
    api: ApiConfig
    raw: dict[str, Any]


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path) if path else REPO_ROOT / "config.yaml"
    data = yaml.safe_load(p.read_text())
    return Config(
        corpus=data["corpus"],
        model=ModelConfig(**data["model"]),
        harness=HarnessConfig(**data.get("harness", {})),
        sandbox=SandboxConfig(**data.get("sandbox", {})),
        api=ApiConfig(**data.get("api", {})),
        raw=data,
    )


@dataclasses.dataclass
class VerifierCommands:
    parse: list[str]
    run: list[str]
    symbols: list[str] | None = None
    # "json" (default): the toolchain prints one JSON document matching
    # 00_ARCHITECTURE.md #5 directly, like PLINTH's CLI does. "text": the
    # toolchain prints human-readable errors (like GnuCOBOL's
    # `file:line: error: message`) and `error_regex` (below) is how the
    # sandbox extracts the #5 shape from that -- corpus-agnostic because
    # the pattern lives in this corpus's meta.yaml, not in ashlar/ code.
    output_format: str = "json"
    error_regex: str | None = None  # required named groups: line, message. optional: file, col, severity


@dataclasses.dataclass
class CorpusSandbox:
    image: str | None = None
    timeout_s: int = 10
    memory_mb: int = 512
    mode: str | None = None  # overrides top-level sandbox.mode when set


@dataclasses.dataclass
class RetrievalConfig:
    bm25_weight: float = 0.75
    embedding_weight: float = 0.25
    chunk_strategy: str = "heading"


@dataclasses.dataclass
class CorpusMeta:
    language: str
    display_name: str
    extension: str
    comment_prefix: str
    verifier: VerifierCommands
    sandbox: CorpusSandbox
    retrieval: RetrievalConfig
    root: Path
    # Excluded from the public /corpora listing (and so from the UI's
    # corpus dropdown) but otherwise fully real and functional -- load_
    # corpus_meta/corpus switch/the verifier all still work by name.
    # "stub" is Phase-0 dev scaffolding, never part of the actual demo;
    # this keeps it hidden from users without deleting it, since a wide
    # swath of the backend's own test suite uses it as a minimal fixture
    # corpus that needs no real toolchain installed.
    hidden: bool = False
    # Sort key for the public /corpora listing (ascending; ties broken by
    # name). Default is high so a corpus that never sets this sorts last,
    # after everything that explicitly claims a demo position.
    order: int = 100


def corpus_dir(name: str, repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / "corpora" / name


def load_corpus_meta(name: str, repo_root: Path = REPO_ROOT) -> CorpusMeta:
    root = corpus_dir(name, repo_root)
    data = yaml.safe_load((root / "meta.yaml").read_text())
    v = data["verifier"]
    s = data.get("sandbox", {})
    r = data.get("retrieval", {})
    return CorpusMeta(
        language=data["language"],
        display_name=data["display_name"],
        extension=data["extension"],
        comment_prefix=data.get("comment_prefix", "#"),
        verifier=VerifierCommands(
            parse=v["parse"],
            run=v["run"],
            symbols=v.get("symbols"),
            output_format=v.get("output_format", "json"),
            error_regex=v.get("error_regex"),
        ),
        sandbox=CorpusSandbox(
            image=s.get("image"),
            timeout_s=s.get("timeout_s", 10),
            memory_mb=s.get("memory_mb", 512),
            mode=s.get("mode"),
        ),
        retrieval=RetrievalConfig(
            bm25_weight=r.get("bm25_weight", 0.75),
            embedding_weight=r.get("embedding_weight", 0.25),
            chunk_strategy=r.get("chunk_strategy", "heading"),
        ),
        root=root,
        hidden=bool(data.get("hidden", False)),
        order=int(data.get("order", 100)),
    )


def effective_sandbox_mode(cfg: Config, meta: CorpusMeta) -> str:
    """Per-corpus meta.yaml sandbox.mode overrides the global default."""
    return meta.sandbox.mode or cfg.sandbox.mode
