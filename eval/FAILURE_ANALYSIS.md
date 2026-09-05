# Failure analysis — PLINTH, live `qwen2.5-coder:3b`

Per `specs/05_EVAL.md` §7. Data sources: `eval/reports/20260905T080555Z.json`
(arm D, repeat=1, pre-retrieval-fix), `eval/reports/20260905T083639Z.json`
(arm D, repeat=3, same code — see the git-SHA caveat below), and live
per-case diagnosis (re-running individual tasks with the full event stream
visible) done during Phase 5. A third, post-retrieval-fix run is referenced
where it changes the picture; see the note at the end.

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

From the repeat=3 report's per-attempt histogram (33 total error
instances across all iterations of all 60 runs):

| Code | Count | Meaning | Repair resolves it? |
|---|---|---|---|
| E001 | dominant, ~30+ | Unexpected token / unknown construct | **Rarely**, when the cause is an invented keyword the model won't abandon (examples-only, composition). **Reliably**, when the cause is a concrete, nameable local mistake (E043-adjacent spacing slips resolve in 1 repair turn). |
| E060 | 3 (all case 017) | Value out of permitted range | No — appears mid-repair as a *new* mistake introduced while attempting to fix the original `angle_mode` conflict, not as the original error. |
| E043 | occasional, first-iteration only | Space between number and unit | **Yes, always** — every case where this is the *first* error ends up passing by the final iteration. |

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

1. Widen `get_examples`/the assembled context so a retrieved comment
   mentioning a construct also pulls in the *actual code line* using it,
   not just the header comment naming it (directly targets §2's remaining
   gap).
2. Trace one composition failure (012) the same way case 009 was traced,
   to find out whether it's the same retrieval-crowding pattern in a new
   shape or a genuinely different cause.
3. Re-run arms A-D at `--repeat 3` on the current (post-retrieval-fix)
   code — the numbers in this document predate those fixes; see
   `LOG.md`'s Phase 5 section for the exact command and why it wasn't
   completed this session (time cost: a full `--repeat 3` sweep across
   A-D was observed to take 25-30 minutes for D alone).
