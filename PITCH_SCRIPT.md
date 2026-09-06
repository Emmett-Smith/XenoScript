# XenoScript pitch video — script and stitching plan

The deck itself lives at `docs/deck/index.html` — a real, navigable HTML
slide deck (not a picture of one), themed identically to the live site and
the actual product UI. This doc is the production plan: how to turn that
deck plus real screen recordings into one finished video with voiceover.

Total run time target: **2:30–3:00**. Twelve slides, most of them fast.

## The two ways to actually produce this

### Option A — one continuous take (fastest, recommended if time is short)

Record yourself presenting the deck live, in real time, reading the
voiceover script below out loud as you advance slides with the arrow keys.
One screen recording, no video editor required.

1. Open `docs/deck/index.html` in Chrome, full-screen (F11 / Cmd+Ctrl+F).
2. Start a screen recording (QuickTime Player → File → New Screen
   Recording, or `Cmd+Shift+5` on macOS).
3. Press `N` once before you start if you want to rehearse against the
   speaker notes drawer — then close it (`N` again) before recording for
   real, since it *would* show up on screen if left open.
4. Advance with → / space, following the script and timings below.
5. For slides 5 and 6 (the live demos): see Option B below for the upgrade,
   or just hold on the slide and narrate over the real screenshot — it's
   real, captured live from the running app, not a mockup.
6. Stop recording. That file is your pitch video. Optionally trim the head
   / tail in QuickTime (Edit → Trim).

### Option B — cut in real live-demo footage (stronger, more time)

Same as A, but before recording the full take, separately record the app
actually running, then splice those clips in during editing instead of
holding on the static screenshot.

1. Confirm the backend + frontend are running: `uv run python -m
   ashlar.api.server` and `cd frontend && npm run dev`.
2. Open `http://localhost:5173`, corpus set to **MUMPS**.
3. Start a screen recording, then type this exact prompt (the same one
   already verified live and used in the deck's slide 5 screenshot):
   > Store the string GARCIA,MARIA^45^F in the uppercase global PATIENT
   > under subscript 40, then write it back out.
4. Let it run to "Verified." Stop recording. This is your slide-5 clip.
5. Switch the corpus dropdown to **COBOL** (no restart needed), and repeat
   with the camera-ready COBOL prompt:
   > Write a COBOL program named GREETER that displays exactly one line of
   > output: "HELLO, ASHLAR."
6. Stop recording. This is your slide-6 clip.
7. In any editor (iMovie, CapCut, DaVinci Resolve — all free), record the
   Option-A full take as your base track, then at the marked points for
   slides 5 and 6, cut away to these two real clips instead of holding on
   the static slide, then cut back.
8. Add the voiceover as a separate audio track if you didn't narrate live
   (see "Voiceover" below), synced to the script timings.

Either option produces a video that never shows fabricated output —
consistent with the project's own rule (see `README.md`, "Known
limitations," and `docs/index.html`'s honesty section): every visual in
this deck is either a real measured number, a real screenshot, or clearly
labeled illustrative.

## Voiceover

If not narrating live during Option A's recording, read the VO lines below
into any voice memo app, or use a TTS tool (macOS: `say` command works in a
pinch for a placeholder track — `say -o slide01.aiff "Validated..."`).
Keep pacing conversational, not sales-y — the deck's own copy is already
plain and specific; don't oversell on top of it.

## Slide-by-slide script

| # | Slide | ~Sec | Voiceover |
|---|---|---|---|
| 1 | Cold open | 12s | "No model was ever trained on the language running your hospital's medical records. This one doesn't need to have been." *(hold on wordmark, 3s)* |
| 2 | The problem | 15s | "MUMPS is almost undocumented in public. It still runs the VA's electronic health records, and much of Epic and Meditech underneath. The developer pool that knows it is shrinking fast, and every general-purpose AI assistant hallucinates its syntax constantly." |
| 3 | The insight | 15s | "We didn't try to fix this with a bigger model. We wrapped whatever local model you already have in a loop that checks its own work against a real toolchain, every single time, before it ever shows you a line." |
| 4 | How it works | 15s | "Retrieve. Generate. Verify. Repair. Cache." *(one beat per card, ~3s each)* |
| 5 | Live demo — MUMPS | 20s | "Same task, live, against the real MUMPS interpreter. It generates, runs it for real, and only shows verified once the real output matches." *(let the clip/screenshot breathe, minimal talking over it)* |
| 6 | Live demo — COBOL | 15s | "Swap the corpus — no restart — and the same architecture runs a completely different language the model already partly knows: COBOL. Same real compiler in the loop." |
| 7 | Languages | 12s | "Adding a language means adding a folder — docs, examples, a toolchain adapter — never new code in the core." |
| 8 | The numbers | 18s | "Plinth is a language we invented for this project. No model has ever seen it. With no help at all, the model gets essentially nothing right: zero percent. With the full loop — retrieve, verify, repair — that same model, same weights, jumps to twenty-five percent." *(let the two numbers sit in silence for 2s before continuing)* |
| 9 | Built by finding real bugs | 15s | "We don't hide the bugs we found. We found them, fixed them, live, and wrote down exactly how." *(optionally add one sentence on the trailing-newline bug — it's the best story)* |
| 10 | Architecture | 12s | "Three local processes: a model server, an MCP tool server over the corpus, and the harness loop that wires them together. Nothing under that harness is allowed to know which language it's talking to." |
| 11 | Try it | 10s | "It runs on your machine. It verifies against a real toolchain. And it shows its work." |
| 12 | Thank you | 6s | "Thank you." *(hold on wordmark for fade-out)* |

**Total: ~185s (≈3:05)** — trim slide 2 or 9 first if you need to land under 3:00.

## Notes on fidelity

- Slides 5/6/8 are the load-bearing "proof" beats — don't rush them.
- The speaker-notes drawer (`N` key) in the deck has a condensed version
  of this same script per slide, for glancing at while presenting live —
  it never appears in a recording of the deck window itself.
- If you add more real screen-recorded footage beyond slides 5/6 (e.g. a
  wider shot of the VS Code sidebar itself, not just the browser), keep it
  real the same way — this project's whole differentiator is that nothing
  shown is faked, and that should hold for the pitch video too.
