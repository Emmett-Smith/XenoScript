# 06 — Demo script, pitch, and Q&A

**Both of you, last two hours. But write the demo script first, on hour one,
and build toward it.** A feature that does not appear in this script is a
feature you should not have built.

---

## 1. The opening line

Lead with lived experience, not architecture. This is the only thing in the
room nobody else can replicate.

> Last summer I wrote simulation code in a language with no public
> documentation, inside a classified environment, with no AI tool that could
> help me — because none of them can see the language, and none of them are
> allowed in the room. That's a few thousand engineers on that one tool. It's
> hundreds of thousands across COBOL, JCL, and internal DSLs at every prime.

Then the claim:

> This makes any undocumented language usable by an AI assistant, offline, in
> under a minute of setup. You give it docs and examples. It gives you code
> that compiles, because it compiles it before showing you.

Do not open with RAG, MCP, or the architecture. Those are answers to questions
you have not been asked yet.

## 2. Demo sequence — 4 minutes

**0:00–0:30 · Ingest.** Drop `corpora/plinth/` in. Counts appear: 52 symbols,
15 examples, 1,412 doc chunks. Say: "This is a language I invented for this
demo. It is provably not in any model's training data — that's the point, and
we measured it."

**0:30–2:00 · A real task.** Type something from the gotcha set. Let the three
columns run live. Narrate only what is on screen:

- Left: it searches the corpus, looks up the symbol, pulls a real example
- Middle: code streams in
- Right: **it fails.** E043, line 7. Then it repairs. Then it passes.

**Do not hide the failure.** The failure is the product. A demo where the
first generation is perfect proves nothing and looks staged. Say: "That's the
part that matters — no model output reaches the user unverified."

**2:00–2:20 · The baseline.** Point at the chart. Arm A near zero, arm D at
whatever you measured. One sentence: "Without the tooling, on a language it
has never seen, it scores near nothing. That gap is the system."

**2:20–2:50 · The undocumented feature.** Run a task requiring
`inherit from`. Point out that it appears nowhere in the manual — the agent
found it by reading example code. "Real legacy documentation is always
incomplete. That's the normal condition, not the edge case."

**2:50–3:20 · Offline.** Turn off wifi. Run another task. It works. "Local
weights, local corpus, no egress. This is designed for an environment where
network access is not a policy question, it's physically absent."

**3:20–4:00 · The swap.** One click: PLINTH → COBOL. Header counts change.
Run a COBOL task, compiled by GnuCOBOL, which we did not write. "Same
codebase, different folder. Adding a language is a corpus, not a rewrite. That
folder could be your internal DSL, and we never see it."

End there. Do not add a roadmap slide.

## 3. What to emphasize for this room

Given senior government officials, model-vendor partners, and lab people:

- **Fieldability over novelty.** Defense judging usually weights deployability.
  You are unusually strong there: no fine-tuning, no egress, swappable model
  endpoint, works on one box. Say "vLLM in the enclave" when asked about real
  hardware.
- **Model-agnostic, deliberately.** Multiple vendors will be sponsors. Position
  as infrastructure any of them would want to plug into, never as a wrapper
  around one. "The model is a base URL in a config file."
- **The constraint is the feature.** Every official there has heard AI pitches
  that die on accreditation. Yours is designed around the constraint instead
  of apologizing for it.
- **Run on local weights, not a hosted API.** If the demo needs internet, the
  central claim dies in front of exactly the people who care most.

## 4. Q&A — prepared answers

**"You invented the language and wrote the verifier. Of course it works."**
Fair, and it's why we ran COBOL too — real language, GnuCOBOL, a compiler we
didn't write. The invented language exists to prove the model has no
memorized knowledge, which we can't prove with COBOL. Two corpora measuring
two different things. *(Volunteer this before it's asked if you can.)*

**"Why not just paste the docs into a long-context model?"**
We measured that — it's arm B on the chart. It scores [X]. It also fails on
anything documented only in examples, and it does not verify output. And a
real corpus is a hundred thousand lines, not a prompt.

**"Isn't this just RAG?"**
Retrieval is the commodity part. The differentiator is the verifier loop and
deriving the symbol table from the toolchain rather than the manual — because
the manual is thirty years stale and the compiler isn't.

**"Does it learn?"**
Verified snippet cache and failure memory. No weight updates, no fine-tuning,
nothing leaves the machine. Here's the cold-versus-warm number. *(Do not
overclaim. The retreat to honesty is stronger than the claim.)*

**"What about a really obscure DSL with twelve example files?"**
Corpus quality is the binding constraint, and we measure it rather than
hand-wave it. Twelve good examples with a working toolchain beats a thousand
pages of prose docs with no compiler. If there's no toolchain to verify
against, we lose the strongest half of the system — that's an honest limit.

**"Could this work on classified corpora?"**
Architecturally yes — that's why it's built with no egress. Practically, ATO
is the timeline, not the code, and that's a program question rather than an
engineering one. We built it so the corpus never leaves the customer's
enclave, which is also why a small team can do this at all.

**"What's your business?"**
The language pack — corpus ingest, symbol extraction from the toolchain,
sandboxed verifier, eval suite for one specific language. Inference is solved
by vLLM. Agent harnesses are commoditizing. The unglamorous per-language work
is what nobody else will do and what open source won't cover for an internal
DSL.

## 5. Optional: live ingest

Highest-risk, highest-payoff move. Have a judge hand you a corpus, or ingest a
real obscure language with a public compiler you never touched during the
build. If it works, the "you built both ends" objection dies permanently and
this becomes the demo people talk about afterward.

Rules if you attempt it: rehearse the mechanics on two unfamiliar corpora
beforehand, keep it to the last 60 seconds, and pre-commit to the framing if
it fails — "that's a corpus with no toolchain to verify against, which is
exactly the limit I described." A gracefully handled failure on a live
unscripted attempt still reads as confidence. An ungracefully handled one
undoes the previous four minutes.

Only attempt this if arms A–E are already recorded and the scripted demo is
solid.

## 6. Rehearsal checklist

- [ ] Full run with **networking physically disabled** — not airplane mode
- [ ] Run on the actual demo laptop, on battery, on a real projector
- [ ] Local model warm-loaded before you walk up; cold model load is 30+ seconds
      of silence
- [ ] Corpus switch tested twice in a row without restart
- [ ] Known-good task list, rehearsed, with a fallback if generation stalls
- [ ] Recorded screen capture of a successful run, on the desktop, as insurance
- [ ] Timer: 4 minutes, out loud, twice
- [ ] `task_failed` state rehearsed — know what you say if it breaks

The recorded capture is not cheating. It is what you play while you debug
live, and having it removes the panic that ruins the pitch.

## 7. Partnership targets at the event

Ranked. Three hallway conversations are worth more than the trophy.

1. **AFRL.** They own the tool that motivated this. A system making
   undocumented simulation languages usable is directly in their interest, and
   they have the corpus we lack. Highest-value conversation available.
2. **Prime engineers — Lockheed, Northrop, Raytheon, and the FFRDCs.** Ask
   about undocumented internal MATLAB toolboxes and in-house DSLs. Known
   language, proprietary undocumented corpus — our architecture serves it
   identically. **The nod you get when you describe that problem is your
   market validation, and it's free.**
3. **Mainframe modernization programs — DFAS, VA, IRS.** COBOL is the door.
   Workforce retirement framing lands instantly with officials.
4. **Model vendors present.** Position as a deployment layer reaching
   environments their hosted products cannot. Complementary, never competitive.
5. **Edge-compute vendors.** Natural bundling — you are the software payload
   for a deployable inference box. Verify who is actually in that market
   before naming anyone on a slide.

For each conversation: ask what they did last week that they hated. Do not
pitch. Get a name and send one paragraph within 24 hours of what you heard
plus one thing you will go find out. That is what converts a hallway
introduction into a contact who answers next time.
