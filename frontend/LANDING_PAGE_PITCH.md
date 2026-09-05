# Project Ashlar

**An AI coding assistant for MUMPS — the language still running the VA's EHR, and much of Epic and Meditech under the hood.**

## The Pitch

Project Ashlar is an AI coding assistant built for MUMPS (M), the decades-old language quietly powering VistA and large parts of Epic and Meditech. Instead of an LLM guessing at syntax it's never reliably seen, Ashlar pairs the model with a real open-source M interpreter that actually compiles and runs every suggestion, then repairs it until the output checks out. It lives where clinical-systems developers already work: a VS Code sidebar, not another browser tab.

## Why This Matters

- Hospitals across the VA network and major EHR vendors still run mission-critical logic in MUMPS written 20-40 years ago, and that code isn't going away anytime soon.
- The developer pool that knows M is shrinking fast — most new engineers have never seen the language, and training pipelines for it are almost nonexistent.
- Tooling is decades behind: no reliable autocomplete, no modern linting, and general-purpose AI coding assistants routinely hallucinate M syntax because they've barely seen it in training data.
- The cost of getting MUMPS code wrong in a clinical system isn't hypothetical — it's patient records, lab orders, and vitals.

## How It Actually Works

- Not a fine-tuned model: Ashlar uses Reference Standard M, a real open-source M interpreter, as ground truth — code is executed, not just pattern-matched.
- Verify-and-repair loop: every generated snippet is run through the interpreter; if it fails to compile or produces the wrong output, Ashlar feeds the error back to the model and retries.
- Behavioral scoring: a curated set of demo prompts is checked against known-correct output, so "correct" means the code actually behaved right — real, verified execution, not a language model's confidence.
- Local backend, local model: the interpreter and model run on your machine, not a hosted black box.
- Ships as a VS Code sidebar extension (webview UI talking to the local backend), so it lives inside a real editor instead of a standalone demo site.

## Try It

1. Install the extension: `code --install-extension ashlar-mumps-assistant-0.0.1.vsix`
2. Start the backend (two terminals): `uv run python -m ashlar.api.server`, and `cd frontend && npm run dev`
3. Click the Ashlar icon in VS Code's activity bar — the sidebar loads automatically once both are running
4. Try one of these example prompts:
   - "Write M code to print a patient's vitals from a global array."
   - "Retrieve and display a lab result value for a given patient ID."
   - "Loop through a patient's recorded vitals and flag any out-of-range readings."

## Honest Caveat

This is a hackathon proof of concept running a small local model with a real verification loop behind it — not a production clinical tool, and not clinically validated.
