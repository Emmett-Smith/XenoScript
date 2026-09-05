"""Loads and templates `prompts/system.md` and `prompts/repair.md`.

03_HARNESS.md #3: prompts are plain text, templated by the harness -- not
model config. We deliberately do NOT use `str.format`: candidate source and
error messages flow into these templates, and DSL source may itself contain
literal `{`/`}` characters, which would raise or corrupt output under
`.format()`. Plain placeholder substring replacement is safe regardless of
what the corpus's language looks like.
"""

from __future__ import annotations

from ashlar.config import REPO_ROOT

PROMPTS_DIR = REPO_ROOT / "prompts"


def _load(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def render(template: str, **kwargs: str) -> str:
    out = template
    for key, value in kwargs.items():
        out = out.replace("{" + key + "}", value)
    return out


def system_prompt(display_name: str, top_failures_block: str = "", corpus_conventions_block: str = "") -> str:
    return render(
        _load("system.md"),
        display_name=display_name,
        top_failures_block=top_failures_block,
        corpus_conventions_block=corpus_conventions_block,
    )


def repair_prompt(current_source: str, errors_with_context: str, symbol_lookups: str) -> str:
    return render(
        _load("repair.md"),
        current_source=current_source,
        errors_with_context=errors_with_context,
        symbol_lookups=symbol_lookups,
    )
