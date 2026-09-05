# Failure analysis — PLINTH, live `qwen2.5-coder:3b`

Per `specs/05_EVAL.md` §7. Data sources: `eval/reports/20260905T080555Z.json`
(arm D, repeat=1, pre-retrieval-fix), `eval/reports/20260905T083639Z.json`
(arm D, repeat=3, same code — see the git-SHA caveat below), live per-case
diagnosis (re-running individual tasks with the full event stream visible)
done during Phase 5, and the final apples-to-apples sweep at commit
`c4dbb6c` (`eval/reports/20260905T092001Z.json` for D; A/B/C from a killed
`--all-arms` run's partial output, numbers below).

## Headline numbers — read this before anything else below

**The single most important finding in this document is a bug in how I
was computing the headline number, not a property of the system.**
`05_EVAL.md` #1 says "D minus C is the verifier's contribution... your
headline claim." Early in Phase 5 that gap looked huge — D=35%, C=5%, a
30-point gap — and it was tempting to report that. **It was wrong**: arm
C (`eval/runner.py`) had its own separate copy of the deterministic
pre-fetch logic, and when Phase 5's retrieval fixes landed in
`ashlar/harness/loop.py` (used by arm D), arm C's copy silently did not
get them. The two arms were no longer measuring the same retrieval
quality, so the "gap" was partly measuring a code-drift bug, not the
verifier loop. Found by comparing before/after eval runs and noticing arm
C hadn't moved when arm D had — fixed by extracting one shared
`deterministic_prefetch()` both arms now call (see `LOG.md` and the
commit dedicated to this fix).

**The corrected, apples-to-apples numbers** (same commit, same corpus,
`--repeat 1` for all four, run same-day within about an hour of each
other on the same machine/model):

| Arm | Verified-correct | Notes |
|---|---|---|
| A (cold) | 0% (0/20) | Consistent across two separate runs today. |
| B (docs pasted) | 0% (0/20) *(varied — see below)* | An **earlier** run of the identical B logic (nothing about B changed between the two runs) scored 5% (1/20). B doesn't call the retrieval pre-fetch at all, so this swing is pure model/run variance, not a code difference — direct evidence for `05_EVAL.md` #4's "single runs at temperature 0.1 still vary." |
| C (tools, no loop) | 20% (4/20) | Up from an earlier, buggy-retrieval 5% — a real improvement, now that C shares D's fixed pre-fetch. |
| D (full system) | 25% (5/20) | Down from an earlier, buggy-retrieval-comparison 35% — see the headline-number note above for why that comparison wasn't valid. |

**D minus C = 5 percentage points**, at n=20, repeat=1. That is the
honest number for tonight. It is much less dramatic than the 30-point gap
that showed up before the arm-C bug was found, and reporting the bigger
number would have been reporting a measurement error, not a result.
**This needs `--repeat 3` before it's a defensible pitch number** — with
swings like B's 5%→0% visible even on a single arm's *unchanged* logic,
n=20/repeat=1 is not enough to trust a 5-point gap either way. Exact
command in `LOG.md`'s morning handoff.

None of this changes §1-4 below, which are about *why* tasks fail, not
*how many* — those patterns held up consistently across every run.

**Provenance caveat, stated plainly:** the repeat=3 report's `git_sha`
field reflects `HEAD` at the moment the report was *written*, not
necessarily the code that was *running* — several commits landed while
that 29-minute background run was in flight. Both `20260905T080555Z.json`
and `20260905T083639Z.json` in fact ran the pre-retrieval-fix code (their
results agree exactly: 35% both times, and the per-case pass/fail pattern
is identical across all 3 repeats within the repeat=3 run — i.e. very low
variance at `temperature=0.1`, at least for these 20 tasks on this model).
Treat this as a caveat for future report-provenance-parsing, not a defect
in the numbers themselves.

## 1. Which of the four gotchas is hardest, and why

Two of the four are effectively unsolved by this model, two are reliably
solved:

- **`set` vs `bind` (5.1)** — solved. Case 005 (natural-language) and case
  016 (repair-from-broken) both pass 3/3. The corpus's own gotcha framing
  ("set assigns a value, bind creates a forward reference") appears to be
  concrete enough, and the retrieved example nearby is close enough in
  shape, for the model to get this right consistently.
- **No space between number and unit (5.4)** — solved. Cases 008 and 015
  both pass 3/3. This is the cheapest gotcha to fix once flagged (per
  `01_LANGUAGE.md` §5.4's own framing) and that holds up empirically: the
  model either gets it right first try or the E043 message ("write
  '1500m' with no space") is concrete enough to fix in one repair turn.
- **Context-sensitive `at` (5.2)** — **hardest**, unsolved, 0/3. Every
  attempt on case 006 ends in `max_iterations` with `E001`. This gotcha
  requires the model to track *which block it's inside* and switch
  between two totally different grammars for the same keyword — a
  structural/contextual distinction, not a vocabulary one, and the error
  message (`E030`/`E031`, spatial-vs-temporal) doesn't hand the model a
  literal fix the way E022 does for bind vs set.
- **`angle_mode` whole-file consistency (5.3)** — **hardest**, unsolved,
  0/3 on both the natural-language case (007) and the repair case (017).
  This is a whole-file invariant, not a local one, and `01_LANGUAGE.md`
  itself calls this out as "exactly the kind of thing models miss." The
  data agrees. Case 017's one occurrence of `E060` (range error, not
  `E042`) suggests the model's repair attempts sometimes veer into a
  *different* mistake (an out-of-range value) rather than converging on
  the original angle-unit fix — the repair loop is not just failing to
  fix the bug, it's occasionally introducing a new one.

**Read:** the two solved gotchas are *local* (fixable by looking at one
line and the field it names). The two unsolved gotchas are *structural*
(the fix requires tracking state across the whole file — which block
you're in, or what the file-wide angle convention is). That distinction,
not the four gotchas' surface difficulty, looks like the real predictor.

## 2. Do examples-only tasks fail on retrieval or on generation?

**Both, but retrieval was the larger and more tractable share of the
problem.** Traced case 009 (`inherit from`) end to end against the real
model, real corpus, real MCP tools (documented in `LOG.md`'s Phase 5
section). Findings, in the order they were found and fixed:

1. **Retrieval bug (found, fixed):** `extract_keywords`'s quoted-string
   regex mis-parsed contractions in the task's own natural-language
   phrasing ("I've seen... I can't find it") as a single ~90-character
   garbage keyword, and `grep_corpus` searched `docs/` before `examples/`
   with one shared limit — so generic keyword hits in `docs/errors.md`
   (matching common structural words like "define"/"platform") exhausted
   the limit before any example file was ever opened. Both fixed in
   `ashlar/harness/keywords.py` and `ashlar/mcp/server.py`.
2. **Retrieval bug (found, fixed):** even restricted to `examples/`, one
   combined alternation pattern with one shared limit let the *first*
   keyword's many matches crowd out a rarer, far more diagnostic
   keyword's single match within the same tier. Fixed by querying
   per-keyword with a fair-share limit in `ashlar/harness/loop.py`.
3. **After both fixes:** the model's context now includes
   `patrol_pair.plth`'s header comment ("demonstrates: inherit from...
   uav_02 copies uav_01's attributes"), and its first-iteration guess
   measurably improved — from inventing an undefined `as` keyword and
   omitting `type air` entirely, to correctly writing `type air` and
   inventing a plausible-but-wrong `copy uav_01` statement instead. That
   is real progress attributable to retrieval, not chance.
4. **What's left is generation, not retrieval:** even with a comment
   literally containing the words "inherit from" in its context, the
   model does not try the word `inherit` across 4 repair iterations — it
   repeats `copy uav_01` verbatim every time. The E001 error for an
   invented keyword can't name a fix the way E022 can for bind-vs-set,
   because the parser has no idea what "copy" was supposed to mean. This
   looks like a genuine capability ceiling on a 3B model for "notice an
   indirect hint in retrieved text and act on it," not a corpus or
   harness defect. Retrieving the *actual code line* using `inherit from`
   (not just a comment naming it) is the next thing worth trying, and
   is not yet done — see "recommended next" below.

## 3. Top three error codes, and whether repair resolves them

From the final apples-to-apples arm-D run's per-attempt histogram (58
total error instances across all iterations of 20 runs, repeat=1;
counting every `verify_result`'s errors, not just each case's last one):

| Code | Count | Meaning | Repair resolves it? |
|---|---|---|---|
| E001 | 42 | Unexpected token / unknown construct | **Rarely**, when the cause is an invented keyword the model won't abandon (examples-only, composition). **Reliably**, when the cause is a concrete, nameable local mistake. |
| E020 | 4 | Unresolved `bind` (target never defined) | Mixed — seen when the model correctly reaches for `bind` but doesn't also define the block it's binding to (see case 003 in §4). |
| E052 | 4 | Required attribute missing | Mixed — the model often fixes the *named* missing attribute, then a *different* required attribute turns out missing on the next iteration (case 005 in §4), suggesting it's patching symptoms rather than reasoning about the whole block's requirements at once. |
| E011 / E042 / E060 / E002 / E022 | 1-2 each | Various | Long tail; too few instances each to generalize, but E042/E060 both showed up as a *new* mistake introduced mid-repair-attempt on the `angle_mode` task, not the original error — worth noting that repair isn't strictly monotonic. |

**Read, updated from the smaller repeat=3-report sample used earlier in
this document:** with the fuller histogram (every attempt, not just each
case's last), the "does the message name a fix" pattern still holds for
the *dominant* code (E001 essentially never resolves for an invented
construct), but the next-most-common codes (E020, E052) reveal a second,
independent pattern: **the model fixes one named problem at a time and
doesn't check whether the fix creates or reveals another one nearby**
(defining a bind target fixes E020 but the sensor is still missing
`range_max`; fixing `range_max` doesn't make it re-check `mount`). This
is a *repair-turn context* finding, not a message-quality one — see
"recommended next steps."

**Read:** repair convergence tracks directly with whether the verifier's
error message can name a concrete fix. E022 (set-on-reference) and E043
(spacing) both name the fix in the message itself, per `01_LANGUAGE.md`
§6's own design intent, and both resolve reliably. E001 for an invented
construct cannot name a fix (there is nothing to name — the parser has
never heard of "copy" or "as" as a statement), and the loop simply
repeats the same wrong guess for the remaining iterations. This is the
strongest evidence in this data set for `01_LANGUAGE.md`'s claim that
"error messages that name the fix dramatically improve repair-loop
convergence" — the inverse holds too: when a message *can't* name a fix,
convergence stops.

## 4. Tasks that never resolve in 4 iterations, and why

13/20 unresolved in the repeat=1 run (identical set across all 3 repeats
in the repeat=3 run — see the provenance note above): 004, 006, 007, 009,
010, 011, 012, 013, 014, 017, 018 (wrong-output, not unresolved-to-parse),
019, 020.

Grouping by cause:

- **Structural gotchas (006, 007, 017):** covered in §1 — whole-file or
  cross-block state the model doesn't track.
- **Examples-only (009, 010, 011):** covered in §2 — real retrieval
  improvement, remaining gap is model capability on indirect hints.
- **Composition (012, 013, 014), all 0/3:** the most surprising finding
  in this data set — these are *not* examples-only or gotcha tasks, just
  "combine 2-3 ordinary blocks correctly," and the model fails all three
  every time. Not fully root-caused this session (time-boxed — see
  `LOG.md`'s handoff); the working hypothesis, based on the same "E001,
  never changes across iterations" signature as the diagnosed
  examples-only case, is that composing multiple blocks correctly
  requires holding more structure in context than a 3B model reliably
  tracks, independent of whether any single construct is novel. Worth a
  dedicated trace in the next session before concluding further.
- **Behavioral (018, 019, 020):** 019/020 are E001/max_iterations (same
  pattern as composition — both are multi-block execute-timeline tasks).
  018 is the one **compiles-but-wrong-output** case in the whole set:
  worth a dedicated look, since "parses clean but produces the wrong
  trace" is a qualitatively different failure than "never parses" and
  might indicate a naming/value mismatch rather than a structural one.

## Recommended next steps (ranked by expected impact)

1. **Re-run `python -m eval.runner --all-arms --corpus plinth --repeat 3`
   on the current code before quoting any number publicly.** Every number
   in this document is `--repeat 1`; observed swings this session (B:
   5%→0% with zero code change) mean a single run per arm is not solid
   ground for a pitch claim, and `05_EVAL.md` #4 asks for `--repeat 3`
   specifically for this reason. The runner now writes its report
   incrementally after each arm (fixed this session after a kill lost an
   in-progress multi-arm run), so this is safe to background and check on.
2. Widen `get_examples`/the assembled context so a retrieved comment
   mentioning a construct also pulls in the *actual code line* using it,
   not just the header comment naming it (directly targets §2's remaining
   gap).
3. Give the repair turn visibility into *all* of a block's required
   attributes when any one is reported missing, not just the one named in
   the current error (directly targets §3's "fixes one thing, breaks/
   reveals another" pattern for E020/E052).
4. Trace one composition failure (012) the same way case 009 was traced,
   to find out whether it's the same retrieval-crowding pattern in a new
   shape or a genuinely different cause.
