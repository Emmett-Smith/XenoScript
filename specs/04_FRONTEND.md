# 04 — Frontend: the demo interface

**Owner: Partner, after the interpreter parses.** Build against
`corpora/stub` and the SSE event contract; you do not need PLINTH to be
finished.

---

## 1. What this screen has to do

One job: **make the verifier loop legible from twenty feet away on a
projector.**

The substance is already visual — tool calls streaming, compile errors
appearing and resolving, an iteration counter dropping. Render the real loop
faithfully and you get "impressive" without decoration. The instinct to make
it shiny is correct; the way to satisfy it is fidelity and pacing, not effects.

Audience: senior government officials and technical judges, in a bright room,
watching for ninety seconds. Assume no one reads a paragraph.

Never fake data. Every pixel is driven by a real SSE event. A judge who
catches a mocked panel discards the entire demo, and rightly.

## 2. Design plan

### Palette (6 values)

```
--paper    #F2F4F5   cool near-white ground; projects clean in a lit room
--ink      #131A2B   deep blue-black; all primary text and structure
--dim      #5A6472   secondary text, line numbers, timestamps
--rule     #BFC6CF   hairlines, block edges
--pending  #B26B00   in-flight: generating, unverified, repairing
--verified #1F5D45   passed the verifier. The only green in the interface.
--fault    #93241F   compile errors
```

Two accents, used with strict meaning: amber is "not yet trustworthy," green
is "verified." Nothing else in the UI may use either color. That discipline is
what makes the state change read instantly at distance.

### Type

**IBM Plex Sans** (UI) + **IBM Plex Mono** (all code, errors, traces).

Chosen for subject reasons, not neutrality: Plex was commissioned by IBM, the
company whose mainframes still run the COBOL this project targets. It carries
the right engineering-documentation register. Self-serve the woff2 files
locally — **no font CDN**, or the offline demo breaks.

If you want a less common pairing, substitute **Roboto Mono** or **Martian
Mono** for code and keep Plex Sans. Do not use a geometric-humanist sans that
reads as generic product UI.

Scale: 13 / 15 / 18 / 24 / 34. Body 15/1.5. Code 13/1.45. Sentence case
everywhere. No all-caps labels.

### Layout — the signal chain

The content genuinely *is* a left-to-right pipeline, so the layout encodes
that rather than decorating it. Three columns, fixed, no scroll on the outer
frame.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Ashlar          PLINTH · 52 symbols · 15 examples · offline    [switch ▾]   │
├────────────────────┬─────────────────────────────┬───────────────────────────┤
│  CORPUS            │  GENERATION                 │  VERIFIER                 │
│                    │                             │                           │
│  grep_corpus       │  1  define scenario coast   │  ┌─────────────────────┐  │
│   "altitude"       │  2    set duration = 60s    │  │  U N V E R I F I E D│  │
│   4 hits           │  3    set step = 0.5s       │  │                     │  │
│  ▸ manual.md:214   │  4  end_scenario            │  │  ▚▚▚ iteration 2/4  │  │
│  ▸ coastal.plth:12 │  5                          │  └─────────────────────┘  │
│                    │  6  define platform uav_01  │                           │
│  lookup_symbol     │  7    set altitude = 1500 m │  E043  line 7             │
│   altitude         │  8  end_platform            │  space between number     │
│   → length         │                             │  and unit                 │
│   → platform,      │  ▌generating…               │                           │
│     waypoint       │                             │  attempt 1  E041 line 14  │
│                    │                             │  attempt 2  E043 line 7   │
│  get_examples      │                             │                           │
│   coastal.plth     │                             │                           │
│   20–24            │                             │                           │
├────────────────────┴─────────────────────────────┴───────────────────────────┤
│  ▸ average the sensor readings across the patrol route            [run]      │
└──────────────────────────────────────────────────────────────────────────────┘
```

Column widths 26% / 42% / 32%. All three left-aligned. Hairline rules between
columns, no cards, no shadows, no border radius above 2px.

Column headings are the only structural labels. Do not add eyebrow labels
above sub-blocks; the indentation and the hairlines already encode hierarchy.

### The one bold element

The **verdict block** in the verifier column. Everything else is quiet,
disciplined, small. The verdict block is large, holds the state word, and is
the only element that changes color.

State machine:

| State | Border | Text | Word |
|---|---|---|---|
| idle | `--rule` | `--dim` | ready |
| generating | `--pending` | `--pending` | generating |
| unverified | `--pending` | `--pending` | unverified |
| repairing | `--pending` | `--pending` | repairing |
| verified | `--verified` | `--verified` | verified |
| failed | `--fault` | `--fault` | not verified |

Below it, the **attempt ledger**: one line per iteration, error code and line
number, accumulating downward. This is the artifact judges will point at,
because it is the proof that the loop is real rather than a single lucky
generation.

### Motion

One orchestrated moment, and it is the transition to verified: the verdict
block's border and text cross-fade amber → green over 400ms while the code
column's error-highlighted line loses its underline. That is it.

No fade-and-slide entrances on panels. No hover transitions on every element.
Token streaming and the error-line underline appearing are motion that answers
a real state change, which is the good kind.

Respect `prefers-reduced-motion`: keep the color change, drop the cross-fade
duration to 0.

### Plan review against generic defaults

Checked against the known AI-design tells before building:

- Not cream + serif + terracotta. Ground is cool, type is Plex, accents are
  earned semantic states rather than decoration.
- **Deliberately not** near-black with a bright accent — that is the default
  for anything terminal-adjacent, and this product is terminal-adjacent, so it
  is exactly the trap here. Light ground also projects better in a lit
  conference room, which is the actual constraint.
- No identical rounded cards, no soft grey shadows, no gradient washes.
- No all-caps eyebrows, no `A · B · C` meta strings, no `→` appended to
  button text.
- Numbered markers appear only on the attempt ledger and code gutter, where
  the content genuinely is a sequence.

The three-column signal chain is the choice most specific to this brief:
column order mirrors the actual data flow, so the layout teaches the
architecture without a diagram. That is the thing to protect if time forces
cuts elsewhere.

## 3. Implementation

Plain **Vite + React + TypeScript**. No component library, no Tailwind config
bikeshedding — write CSS. Roughly 600 lines total.

```
frontend/src/
  App.tsx
  useTaskStream.ts        # EventSource → typed reducer over the §8 events
  panels/CorpusPanel.tsx
  panels/CodePanel.tsx
  panels/VerifierPanel.tsx
  panels/PromptBar.tsx
  panels/BaselineChart.tsx
  styles.css              # tokens as CSS custom properties
```

`useTaskStream` is the whole app's state. One reducer, one event union type
matching `00_ARCHITECTURE.md` §8. If the event contract and this type ever
disagree, the contract wins.

### Code panel specifics

- Line numbers in `--dim`, monospace, right-aligned, no gutter background.
- Errors: 2px `--fault` underline on the offending line, code badge in the
  right margin. Not a red background fill — it obscures the code, which is
  the thing people are trying to read.
- Streaming: append tokens directly, no typewriter simulation. Real speed is
  more convincing than a fake cadence, and local models are already dramatic
  enough.
- Auto-scroll to the error line when `verify_result` arrives with errors.

### Corpus panel specifics

Render each tool call as it happens: tool name in mono, arguments, result
count, then up to three result lines with `file:line`. Collapse older calls to
a single line so the panel doesn't overflow during a four-iteration run.

This panel is the answer to "is it actually retrieving or just guessing," and
someone will ask.

### Baseline chart

Small, bottom of the verifier column or a toggled overlay. Three bars, no
axis decoration, values labeled directly:

```
no tools, local model      ▏ 5%
tools, local model         ██████████ 87%
tools, cloud model         ███████████ 93%
```

Read from `GET /eval/latest`. Never hardcode the numbers — they will change,
and a stale hardcoded chart is the kind of thing that gets noticed.

### Corpus switcher

Header dropdown, `POST /corpus/switch`. On switch, header counts update and
all three panels clear. This is the demo's closing move; it must be one click
and it must be visibly instant.

## 4. Cut list, in order

1. Baseline chart as an overlay → move inline, static from last eval JSON
2. Collapsing of older tool calls → just let it scroll
3. Reduced-motion handling → keep the color change only
4. Corpus switcher animation → hard swap

Never cut: the verdict block, the attempt ledger, the error underline, the
corpus panel's live tool calls.

## 5. Definition of done

- [ ] Every panel driven by real SSE events; zero mocked data paths in the build
- [ ] Verdict block transitions correctly through all six states
- [ ] Attempt ledger accumulates and persists after `task_done`
- [ ] Error line underline + code badge render from `verify_result`
- [ ] Legible at 1280×720 scaled to a projector — test on a real projector
- [ ] Fonts served locally; page renders with networking disabled
- [ ] Corpus switch clears panels and updates header counts in one click
- [ ] Baseline chart reads from the API, no hardcoded values
- [ ] Visible keyboard focus on the prompt bar and both controls
- [ ] `task_failed` renders a readable state, not a spinner
