# Getting started with XenoScript

You just downloaded the **XenoScript VS Code extension**. Before it does
anything, three things need to be running on your machine: a local model
(Ollama), the Python backend, and the frontend dev server. The extension
itself is a thin sidebar that displays the frontend — it has no logic of its
own.

This takes about 10-15 minutes the first time, mostly waiting on installs.

## 0. What you need

- macOS (Apple Silicon or Intel) or Linux. Windows/WSL untested.
- [Ollama](https://ollama.com) — runs the local model, fully offline after
  the first pull.
- [`uv`](https://docs.astral.sh/uv/) — Python dependency manager
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- Node.js 20+ and npm (for the frontend).
- VS Code.

## 1. Clone the project

The extension alone can't verify or run any code — it needs the real
backend + toolchains from the GitHub repo.

```bash
git clone https://github.com/Emmett-Smith/XenoScript.git
cd XenoScript
```

## 2. Install and start Ollama

```bash
ollama pull qwen2.5-coder:3b     # the model config.yaml is set to use
ollama serve                     # if it isn't already running as a background service
```

## 3. Start the backend

```bash
uv sync
uv run python -m ashlar.api.server     # http://localhost:8000
```

Leave this running in its own terminal.

## 4. Start the frontend

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

Leave this running too. At this point you can open `http://localhost:5173`
directly in a browser and it already works, no VS Code needed.

## 5. Install the extension

Open the `.vsix` you downloaded from the website, or from a terminal:

```bash
code --install-extension xenoscript-mumps-assistant-0.0.1.vsix
```

Reload VS Code. Click the XenoScript icon in the Activity Bar — the sidebar
loads the running frontend automatically. If the sidebar is blank, check
steps 3 and 4 are both still running.

## 6. Pick a corpus and try a prompt

The corpus dropdown at the top defaults to `plinth` (a synthetic language,
fastest to try since it needs no extra toolchain install). To try the two
demo languages:

- **COBOL** — works immediately if you have GnuCOBOL:
  `brew install gnucobol` (macOS) or `apt install gnucobol` (Linux). Try:
  > Write a COBOL program named GREETER that displays exactly one line of
  > output: "HELLO, ASHLAR."
- **MUMPS** — the lead demo (MUMPS still runs much of the VA's and Epic's
  EHR systems), but its interpreter has to be built from source, it isn't
  bundled in the repo:
  ```bash
  git clone https://github.com/Reference-Standard-M/rsm.git /tmp/rsm
  cd /tmp/rsm && make
  mkdir -p <XenoScript repo>/.toolchains/rsm/bin
  cp rsm <XenoScript repo>/.toolchains/rsm/bin/rsm
  ```
  Then switch the corpus dropdown to `mumps` and try:
  > Store the string GARCIA,MARIA^45^F in the uppercase global PATIENT
  > under subscript 40, then write it back out.

Switching corpora in the dropdown is live — no backend restart needed.

## Troubleshooting

- **Sidebar shows nothing / spinner forever**: confirm `curl
  localhost:8000/corpora` and `curl localhost:5173` both respond. The
  extension is only a viewer for those two local servers.
- **Model requests time out**: `ollama list` should show
  `qwen2.5-coder:3b`; `ollama serve` must be running.
- **MUMPS-specific `make` failure**: RSM's own build only supports
  Linux/macOS — Windows needs WSL.

## Honest caveat

This is a hackathon proof of concept: a small local model plus a real
verify-and-repair loop, not a production or clinically-validated tool.
