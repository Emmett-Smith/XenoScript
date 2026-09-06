# XenoScript pitch video — script and stitching plan

The deck itself lives at `docs/deck/index.html` — a real, navigable HTML
slide deck (not a picture of one), themed identically to the live site and
the actual product UI. This doc is the production plan: how to turn that
deck into one finished video with voiceover.

Total run time target: **~2:30**. Eleven slides, most of them fast — one
of them (Live demo) plays a real, embedded screen recording rather than
being timed by voiceover.

## Producing it — one continuous take (recommended)

Record yourself presenting the deck live, in real time, reading the
voiceover script below out loud as you advance slides with the arrow keys.
One screen recording, no video editor required.

1. Open `docs/deck/index.html` in Chrome, full-screen (F11 / Cmd+Ctrl+F).
2. Start a screen recording (QuickTime Player → File → New Screen
   Recording, or `Cmd+Shift+5` on macOS). Make sure system audio is
   captured too, since slide 5's video has its own sound.
3. Press `N` once before you start if you want to rehearse against the
   speaker notes drawer — then close it (`N` again) before recording for
   real, since it *would* show up on screen if left open.
4. Advance with → / space, following the script and timings below.
5. On slide 5 (**Live demo**), click play on the embedded video
   (`docs/deck/assets/final-demo.mp4` — the real `FINAL DEMO.mov` capture)
   and let it run to completion before advancing. This is real, unedited
   footage: no separate recording step needed anymore.
6. Stop recording. That file is your pitch video. Optionally trim the head
   / tail in QuickTime (Edit → Trim).

This produces a video that never shows fabricated output — consistent with
the project's own rule (see `README.md`, "Known limitations," and
`docs/index.html`'s honesty section): every visual in this deck is either a
real measured number, a real screenshot, real recorded footage, or clearly
labeled illustrative.

## Voiceover

For every slide except the Live demo (which carries its own recorded
audio), read the VO lines below into any voice memo app if not narrating
live, or use a TTS tool (macOS: `say` command works in a pinch for a
placeholder track — `say -o slide01.aiff "Validated..."`). Keep pacing
conversational, not sales-y — the deck's own copy is already plain and
specific; don't oversell on top of it.

## Slide-by-slide script

| # | Slide | ~Sec | Voiceover |
|---|---|---|---|
| 1 | Cold open | 12s | "Every classified program has languages that can't leave the room. No public docs. No training data. No cloud AI allowed anywhere near them. This is built for exactly that case." *(hold on wordmark, 3s)* |
| 2 | The problem | 15s | "Last summer, someone on this team wrote simulation code in a language with no public documentation, inside a classified environment, with no AI tool that could help — because none of them can see the language, and none of them are allowed in the room. That's not rare. It's every branch, every agency, every prime with an internal DSL." *(pause after "allowed in the room")* |
| 3 | The insight | 15s | "We didn't try to fix this with a bigger model. We wrapped whatever local model you already have in a loop that checks its own work against a real toolchain, every single time, before it ever shows you a line." |
| 4 | How it works | 15s | "Retrieve. Generate. Verify. Repair. Cache." *(one beat per card, ~3s each)* |
| 5 | **Live demo** | ~48s | *(no VO needed — this is the real `FINAL DEMO.mov` recording, embedded and playing with its own audio: "Add Maria Garcia, who is 45 to the patients database," generated, run against Reference Standard M, verified, live in VS Code.)* Say one line before pressing play — "We can't film a classified language, so here's the same architecture on a real, publicly-undocumented one" — then go quiet and let it run. |
| 6 | Languages | 14s | "Three proof points, not three products. Adding a language means adding a folder — docs, examples, a toolchain adapter — never new code in the core." |
| 7 | The numbers | 18s | "Plinth is a language we invented for this project. No model has ever seen it — the closest public stand-in for an actual classified DSL. With no help at all, the model gets essentially nothing right: zero percent. With the full loop — retrieve, verify, repair — that same model, same weights, jumps to twenty-five percent." *(let the two numbers sit in silence for 2s before continuing)* |
| 8 | Built by finding real bugs | 15s | "We don't hide the bugs we found. We found them, fixed them, live, and wrote down exactly how." *(optionally add one sentence on the trailing-newline bug — it's the best story)* |
| 9 | Architecture | 14s | "Three local processes: a model server, an MCP tool server over the corpus, and the harness loop that wires them together. All three run on-box, no network call required at any point. Nothing under that harness is allowed to know which language it's talking to." |
| 10 | Try it | 10s | "It runs on your machine, air-gapped. It verifies against a real toolchain. And it shows its work." |
| 11 | Thank you | 6s | "Thank you." *(hold on wordmark for fade-out)* |

**Total: ~178s (≈3:00)**, dominated by slide 5's ~48s real video — trim
slide 2 or 8 first if you need more headroom.

## Notes on fidelity

- Slides 5 (live demo) and 7 (the numbers) are the load-bearing "proof"
  beats — don't rush past either.
- The speaker-notes drawer (`N` key) in the deck has a condensed version
  of this same script per slide, for glancing at while presenting live —
  it never appears in a recording of the deck window itself.
- Slide 5's video is real, unedited, and has audio (system/UI sound from
  the original recording) — check your screen-recording setup captures
  that audio too, or the moment will play silently.
