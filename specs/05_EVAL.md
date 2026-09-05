# 05 — Eval: baselines, arms, and the numbers you present

**Owner: either, but do it early.** The baseline is not a nice-to-have. It is
the difference between a demo and a result. "It works" is a demo. "Baseline
5%, ours 87%" is a result, and results win.

Budget two hours for the baseline arm before building any tooling.

---

## 1. Arms

Five configurations, same 20 tasks. Run all of them; report all of them.

| Arm | Model | Corpus access | Verifier loop |
|---|---|---|---|
| A — cold | local | none | no |
| B — docs in prompt | local | full docs pasted, no tools | no |
| C — tools, no verifier | local | MCP tools | no |
| D — full system | local | MCP tools | yes |
| E — full, cloud model | cloud | MCP tools | yes |

What each arm is for:

- **A** proves the language is genuinely unseen. On PLINTH this should be
  near 0%. That number is the entire justification for inventing a language,
  so measure it and lead with it.
- **B** is the honest competitor. If long-context-with-docs-pasted scores
  well, retrieval is dead weight and you need to know that before the event,
  not during Q&A. **Do not skip B.** It is the arm a sharp judge will ask
  about.
- **C** isolates retrieval from verification. Expect a modest lift over B.
- **D** is the product.
- **E** shows the ceiling and tells the audience what hardware buys them.

D minus C is the verifier's contribution. That gap is your headline claim, so
make sure the harness logs enough to defend it.

## 2. Task set

20 tasks in `eval/cases/`, each:

```
eval/cases/007/
  task.txt        # natural language, phrased as a user would
  expected.txt    # exact interpreter trace, or null if compile-only
  rubric.yaml     # grading config
```

```yaml
# rubric.yaml
grade: compile_and_run     # compile_only | compile_and_run
max_iterations: 4
tags: [bind, forward_reference]
must_contain: ["bind"]     # optional, use sparingly
must_not_contain: ["set primary_sensor"]
```

Distribution — deliberate, not accidental:

| Count | Category | Notes |
|---|---|---|
| 4 | basic structure | single block, required attributes |
| 4 | the four gotchas | one each: set/bind, context `at`, angle_mode, spacing |
| 3 | examples-only features | `inherit`, `every ... for` — docs cannot help |
| 3 | multi-block composition | platform + sensor + execute |
| 3 | repair from broken input | given source with seeded errors, fix it |
| 3 | behavioral | must produce exact expected trace output |

The three examples-only tasks are the most important in the set. They are
unsolvable from documentation alone, so they measure exactly what the system
claims to do: recover undocumented grammar from example code. Report them as
their own line.

## 3. Metrics

Primary: **verified-correct rate** — compiled clean, and where a rubric
specifies `compile_and_run`, produced the expected trace.

Secondary:

- Mean iterations to verified (D and E only)
- First-attempt pass rate
- Error-code histogram across all attempts — feeds failure memory and tells
  you which gotcha is hardest
- Wall-clock per task, p50 and p95
- Tool calls per task
- Unresolved-after-4 count

Report format, `eval/reports/<timestamp>.json`, and a markdown table for the
slide. `GET /eval/latest` serves the JSON to the frontend chart.

## 4. Running it

```
python -m eval.runner --arm D --corpus plinth --repeat 3
python -m eval.runner --all-arms --corpus plinth --repeat 3
```

- `--repeat 3` and report mean plus range. Single runs on local models at
  temperature 0.1 still vary, and a judge asking "did you run it more than
  once" should get a yes.
- **Every report records the model name, endpoint, and git SHA.** Non-negotiable.
  A number without provenance is worthless and you will lose track of which
  arm produced what.
- Runner must work offline for arms A–D.

## 5. The learning-curve demo

This is the honest version of "it learns," and it demos well.

```
python -m eval.runner --arm D --corpus plinth --cache-cold
python -m eval.runner --arm D --corpus plinth --cache-warm
```

Cold: empty `verified_cache` and `failures`. Warm: after running the other 15
non-eval pair tasks so the cache holds real verified snippets and failure
memory holds the common error codes.

Expected effect: mean iterations drops, and first-attempt pass rate rises.
Report both numbers.

On stage, the live version is one task run twice — once cold, once after the
cache has entries. Iteration count visibly drops from 3–4 to 1. Then say
plainly: no weight updates, no data leaving the machine, just verified
examples accumulating on local disk. That framing is stronger than "it learns"
because it is exactly what makes the thing deployable in a closed
environment.

## 6. The COBOL arm — answering the strongest objection

The objection you will get: **"you invented the language and you wrote the
verifier, so of course it passes."** It is fair, and it is the single biggest
threat to the demo.

Three answers, build as many as time allows:

1. **Run arms A–D on `corpora/cobol`.** Real language, real compiler
   (`cobc`) that we did not write, real stakes. 10 tasks is enough. This is
   the factual rebuttal and it is worth more than any additional feature.
2. **Publish arm A openly.** Do not bury the near-zero baseline; lead with it.
   Explain that the invented language exists specifically to prove absence of
   memorization. A judge who hears this reasoning from you will not raise it
   as a gotcha.
3. **Live ingest of something unprepared.** Highest risk, highest payoff — see
   `06_DEMO.md` §5. If it works, it ends the objection permanently.

Note honestly in the report that COBOL arm A will *not* be near zero, because
COBOL is in training data. That is the point: the two corpora measure
different things. Synthetic proves no memorization; COBOL proves real-world
applicability. Say so.

## 7. Failure analysis you will be asked for

Keep a short written analysis, one paragraph per category:

- Which of the four gotchas is hardest, and why
- Whether examples-only tasks fail on retrieval or on generation
- What the top three error codes are and whether repair resolves them
- The tasks that never resolve in four iterations, and your read on why

Judges and, later, prime engineers ask "where does it break." Having a crisp
answer is a credibility multiplier. "We don't know yet" is acceptable;
"it always works" is not, and nobody believes it.

## 8. Definition of done

- [ ] 20 cases written, distribution per §2
- [ ] Arm A run and recorded — this is the first number you need
- [ ] Arm B run — the honest long-context competitor, not skipped
- [ ] Arms C, D, E run with `--repeat 3`
- [ ] Every report stamped with model, endpoint, git SHA
- [ ] Cold vs warm cache comparison recorded
- [ ] COBOL corpus, 10 cases, arms A–D
- [ ] `GET /eval/latest` serves the report the frontend chart reads
- [ ] Arms A–D reproducible with networking disabled
- [ ] Written failure analysis, one paragraph per §7 bullet
