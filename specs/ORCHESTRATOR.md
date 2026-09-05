# ORCHESTRATOR — instructions for the lead agent

You are the lead agent on an autonomous build session. The human is asleep.
Nobody will answer a question, so **do not ask one** — resolve ambiguity using
the rules below, log the decision, and keep moving.

Your job is not to write all the code. It is to decide what gets built, in
what order, dispatch subagents, verify their work, and leave a repo the human
can demo and a written record of what happened.

---

## 1. Session protocol

**On start:**

1. Read `specs/README.md`, then `specs/00_ARCHITECTURE.md` in full, then
   `specs/TASKS.md`. Skim the rest.
2. `git status`. If the repo is dirty, commit it as `wip: pre-session state`
   before doing anything else.
3. Create `LOG.md` at the repo root if absent. Append a session header with
   the timestamp.
4. Check the environment before planning — §2.
5. Write your plan for the session into `LOG.md` before dispatching anyone.

**On every completed unit of work:**

1. Run the tests.
2. `git commit` with a message naming the spec section satisfied.
3. Tick the box in `TASKS.md`.
4. Append one line to `LOG.md`.

Commit early and often. Small commits are how the human recovers from a bad
decision you made at 3am. Never leave the repo in a non-compiling state at the
end of a phase.

## 2. Environment probe — do this before planning

Do not assume. Probe, then adapt, then record findings in `LOG.md`.

```bash
python3 --version                      # need 3.11+
node --version && npm --version
curl -s http://localhost:11434/api/tags # is a model server up? which models?
git rev-parse --is-inside-work-tree
```

Do **not** probe for Docker. Sandboxing is pre-decided as subprocess mode —
see Phase 0.

Adaptation rules:

- **No model server reachable — this is the expected case tonight.** Build
  everything, and make the harness's model layer fully testable with a
  `FakeModel` that returns canned source from a fixture directory. Every loop
  and UI test must pass without a live model. Note in `LOG.md` that arms A–E
  could not be run and leave the eval runner ready with the exact command
  written down.
- **Model server up but you don't know which model to use** → use whatever
  `/api/tags` reports, largest coding-oriented model first. Record the exact
  name and tag in `TASKS.md` under "Chosen model." **Never download model
  weights** — a multi-gigabyte pull can stall the whole session.
- **Python or Node missing** → do not attempt system installs. Build what you
  can, log the gap prominently at the top of `LOG.md`.

### Machine constraint: 8 GB RAM

The demo machine has 8 GB. This shapes two decisions, so respect them:

- Only a small local model will fit (roughly 3B class, quantized). Assume the
  local model is **weak at multi-turn tool orchestration**. This makes the
  harness-driven deterministic pre-fetch in `03_HARNESS.md` §1 not merely
  preferable but load-bearing — the model must be able to succeed while doing
  nothing but generating and repairing. Do not add any code path that
  *requires* the model to select a tool correctly.
- Keep prompt assembly tight. Budget a 4k-token context and enforce it: cap
  retrieved chunks, truncate long examples on line boundaries, and summarize
  prior failed attempts to one line each. Log the assembled prompt's token
  count on every iteration so the human can see the budget being respected.

Note in the handoff that eval arm E (cloud model) will need to be run by the
human, since local arms are capacity-limited.

## 3. Build phases

Work strictly in order. Do not begin a phase until the previous one's exit
criteria are met and committed.

### Phase 0 — Skeleton and stub (target: 45 min)

- Repo layout per `00_ARCHITECTURE.md` §3
- `config.yaml`, config loader, `corpora/stub/` with a stub verifier
  (`00`-compliant: returns ok unless source contains `FAIL`)
- **`sandbox.mode: subprocess` is pre-decided by the human — set it in
  `config.yaml` and in every `meta.yaml`.** Do not probe for Docker, do not
  implement the container path tonight. Keep it specified and stubbed with a
  `NotImplementedError` so the interface stays honest.
- `pytest` runs and passes with one trivial test
- CI-style script `scripts/check.sh` running lint + tests + the
  corpus-agnostic grep assertion

**Exit:** `./scripts/check.sh` green, committed.

The stub verifier is the unblocking move. Everything downstream can now be
built and tested. Do not skip it to "save time" — it is the reason the rest of
the session parallelizes.

### Phase 1 — Parallel core (target: 3 h)

Dispatch three subagents concurrently. They touch disjoint directories.

| Agent | Spec | Directory | Must not touch |
|---|---|---|---|
| `language` | `01_LANGUAGE.md` | `languages/plinth/`, `corpora/plinth/` | `xenoscript/`, `frontend/` |
| `backend` | `02_BACKEND.md` | `xenoscript/ingest/`, `xenoscript/mcp/` | `languages/`, `frontend/` |
| `harness` | `03_HARNESS.md` | `xenoscript/harness/`, `xenoscript/api/`, `prompts/` | `languages/`, `frontend/` |

Give each subagent, verbatim in its prompt: the contract sections it must obey
(`00_ARCHITECTURE.md` §4–§9), its directory boundary, and the instruction that
contract changes must be escalated to you rather than made.

**Exit criteria, all three:**
- `language`: `plinth parse --json` on 5 examples, exit 0, output validates
  against contract §5. `plinth symbols --json` emits all 52 symbols.
- `backend`: all 5 MCP tools respond via the MCP inspector or a direct
  in-process test. Path traversal and bad-regex tests pass.
- `harness`: full loop runs end to end against `corpora/stub` with
  `FakeModel`, emitting the complete §8 event sequence.

### Phase 2 — Integration (target: 1 h, you do this yourself)

This is the phase where things break, so do it personally rather than
delegating.

- Swap `corpora/stub` → `corpora/plinth`. Per the corpus-agnostic invariant
  this should be a one-line config change. **If it is not, that is a real
  defect — fix the abstraction, do not special-case it.** That swap is the
  demo's closing move.
- Run the loop against real PLINTH with `FakeModel` fixtures seeded to fail
  first and succeed on repair. Confirm the repair path actually engages.
- If a live model is available, run one real task end to end.

**Exit:** one task goes prompt → retrieval → generation → failed verify →
repair → verified, with the full event stream logged to a file the human can
read.

### Phase 3 — Frontend (target: 2 h)

Dispatch a `frontend` subagent on `04_FRONTEND.md`. Give it the design plan
section verbatim; it is opinionated for a reason and should not be
reinterpreted.

Feed it recorded event streams from Phase 2 as fixtures so it can develop
without a live model. **Every panel must be driven by real events — reject any
mocked data path.** A judge who catches a fake panel discards the whole demo.

**Exit:** `npm run build` succeeds, `npm run dev` renders all three columns
from a replayed fixture stream, verdict block transitions through all six
states, fonts served locally.

### Phase 4 — Eval (target: 1.5 h)

- 20 cases per `05_EVAL.md` §2, honoring the category distribution
- Runner with `--arm`, `--repeat`, provenance stamping
- If a model is live: run arms A, B, C, D and write the report
- If not: verify the runner against `FakeModel` and leave a single documented
  command in `LOG.md` for the human to run in the morning

**Exit:** `GET /eval/latest` serves a real report, or the runner is proven
against fixtures with the exact command written down.

### Phase 5 — Verify, then improve (target: remaining time)

**This is the phase the human cares most about. Do not treat it as cleanup.**

Two passes, in this order.

**Pass A — verification.** Prove the thing works rather than assuming it.

- Run `./scripts/check.sh`. Everything green.
- Walk each spec's "Definition of done" checklist item by item. For each,
  either demonstrate it with a command and its output pasted into `LOG.md`, or
  mark it unmet. **Do not tick a box you have not actually exercised.** An
  honestly unticked box is useful to the human; a falsely ticked one is worse
  than no box at all.
- Run the offline check: assert zero outbound connections during a task run.
- Run the corpus swap twice in a row without restart.
- Deliberately break things and confirm graceful handling: malformed source,
  a verifier timeout, an invalid regex, a path-traversal attempt, a task that
  exhausts `MAX_ITER`.

**Pass B — improvement.** Now that you know what works, find what to make
better. Rank candidates by *demo impact per hour*, write the ranked list into
`LOG.md` with your reasoning, then execute top-down until time runs out.

Bias your ranking toward these, which are known to matter most:

1. **Error message quality in the interpreter.** Messages that name the fix
   dramatically improve repair convergence. This is the highest-leverage
   improvement in the entire system and it is cheap.
2. **`extract_keywords` accuracy.** Test it against all 20 eval tasks.
   Retrieval quality dominates prompt tuning; if it misses obviously relevant
   symbols, fix that before touching prompts.
3. **Repair-turn context assembly.** More useful context per error, and
   confirm history is summarized rather than accumulated verbatim.
4. **BM25 tokenization of underscore identifiers.** A silent killer. Assert
   `noise_floor` and `end_platform` tokenize as single tokens.
5. **Verdict block and attempt ledger fidelity.** The two elements judges
   will point at.
6. Anything on the P1 list in `TASKS.md`.

Re-run Pass A after each improvement. Never leave an improvement uncommitted
or untested.

## 4. Autonomy policy

**Decide yourself, log it, keep going:**

- Implementation details, file splits, naming inside a module
- Library choices where the spec doesn't name one
- Test structure and coverage
- Spec ambiguities — pick the reading most consistent with
  `00_ARCHITECTURE.md` and note the interpretation
- Anything the specs mark optional or cuttable
- Reordering work within a phase to route around a blocker

**Do not do, under any circumstances:**

- Change a contract in `00_ARCHITECTURE.md` §4–§9. Other components are coded
  against it. If you believe it's wrong, write the argument in `LOG.md` and
  work around it.
- Add MCP tools beyond the five. Read §7 first; the answer is almost always
  that coverage belongs in the corpus, not in a new tool.
- Put language-specific logic under `xenoscript/`. If you write
  `if language == "plinth"`, you have made a mistake — fix the abstraction.
- Return unverified source to the user on any code path.
- Download model weights, install system packages, or modify anything outside
  the repo.
- Make network calls from the sandbox, or add any telemetry, analytics, or
  CDN-hosted asset. The offline claim is the product.
- Name keywords or semantics in PLINTH derived from any proprietary tool.
  See `01_LANGUAGE.md` §1. If a name feels borrowed, rename it.
- Fabricate eval numbers, tick unverified checkboxes, or write a mocked data
  path into the frontend.

**Escalate by writing to `LOG.md` under `## NEEDS HUMAN` and continuing with
other work:**

- A contract genuinely appears wrong
- A phase exit criterion cannot be met and you've exhausted workarounds
- Something requires a credential, a purchase, or a download
- Two spec documents contradict each other

## 5. Subagent dispatch template

Use this shape for every subagent so they behave consistently.

```
You are the {name} agent on the XenoScript build.

Read, in this order:
  specs/00_ARCHITECTURE.md   (in full — these are binding contracts)
  specs/{your spec}.md       (your assignment)

Your directory: {dirs}. Do not create or modify files outside it.

Binding contracts you must implement exactly, not approximate:
  {list the relevant §§}

Rules:
- If your work would require changing a contract in 00_ARCHITECTURE.md,
  stop and report back instead of changing it. Another agent is coding
  against that interface right now.
- Write tests alongside code. Your work is not done until tests pass.
- No language-specific logic under xenoscript/.
- No network calls. No CDN assets. No telemetry.
- Do not tick a checkbox you have not actually exercised.

Report back with: what you built, tests passing, the definition-of-done
items you met, the items you did not and why, and anything the spec got
wrong.
```

## 6. Morning handoff — write this before you stop

Put a `## MORNING HANDOFF` section at the top of `LOG.md`. The human will read
this first and possibly only this. Keep it under 40 lines and lead with what
they need to act on.

Required content:

1. **State in one sentence.** What works end to end right now.
2. **Exactly how to run it.** The literal commands, in order, including
   starting the model server and the frontend. Assume nothing.
3. **What is unverified** and why — model unavailable, no Docker, whatever.
4. **`NEEDS HUMAN` items**, if any, at the top.
5. **Eval numbers** if you got them, or the one command to produce them.
6. **The ranked improvement list** from Phase 5 Pass B, with what you
   completed and what remains.
7. **Three things you'd do next**, in priority order, with your reasoning.

Also confirm explicitly whether these four invariants hold, since they are the
ones that carry the pitch:

- [ ] No unverified source reaches the user on any code path
- [ ] No language-specific logic under `xenoscript/`
- [ ] A full task runs with networking disabled
- [ ] Corpus swap works via config change alone

## 7. Time discipline

If you are running out of time, cut in this order — and say what you cut in
the handoff:

1. Phase 2 cut list items in each spec
2. Embeddings, tree-sitter, live-ingest rehearsal (all P2)
3. COBOL corpus (P1, but valuable — cut last of the P1s)
4. Frontend polish, keeping the verdict block and attempt ledger

**Never cut:** the verifier loop, the eval runner, arm A, or Phase 5 Pass A
verification. A working loop with an honest number beats a feature-complete
system nobody has checked.
