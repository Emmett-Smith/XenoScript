# XenoScript — MUMPS AI Assistant (VS Code extension)

XenoScript is an AI coding assistant for MUMPS, the language behind most EHR
systems (Epic, VistA, Meditech). This extension embeds XenoScript's existing
Vite/React frontend in a VS Code sidebar panel so it can be used without
leaving the editor.

This extension is a thin shell: it does not reimplement XenoScript's UI. It
loads the already-running frontend (`http://localhost:5173`) in a webview
iframe. You must have the backend and frontend dev servers running for the
panel to show anything.

## Prerequisites

- Node.js (v18+ recommended) and npm
- The [XenoScript](https://github.com/) repo checked out locally (this
  extension lives at `vscode-extension/` inside it)
- [`uv`](https://docs.astral.sh/uv/) installed, for running the Python
  FastAPI backend (`ashlar/api/server.py`)
- (If the backend uses a local LLM) [Ollama](https://ollama.com/) installed

## 1. Start the backend and frontend

From the root of the XenoScript repo, in separate terminals:

```bash
# Terminal 1 — local model server (only if the backend needs it)
ollama serve

# Terminal 2 — XenoScript FastAPI backend, served at http://127.0.0.1:8000
uv run python -m ashlar.api.server

# Terminal 3 — XenoScript Vite/React frontend, served at http://localhost:5173
cd frontend
npm run dev
```

Leave all of these running. The extension does not start them for you.

## 2. Build and install the extension

From `vscode-extension/`:

```bash
npm install
npm run compile
npm run package   # produces xenoscript-mumps-assistant-<version>.vsix
```

Then install the generated `.vsix` file with either:

```bash
code --install-extension xenoscript-mumps-assistant-<version>.vsix
```

or, inside VS Code: open the Extensions view (`Cmd+Shift+X` /
`Ctrl+Shift+X`), click the `...` menu at the top, and choose
**"Install from VSIX..."**, then select the `.vsix` file.

## 3. Open the XenoScript sidebar

With the backend and frontend running and the extension installed, either:

- Click the **XenoScript** icon in the VS Code Activity Bar (left-hand sidebar), or
- Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) and run
  **"XenoScript: Open Assistant"**.

If the panel appears blank, the backend/frontend dev servers likely aren't
running yet — the panel shows a fallback notice, or you can run
**"XenoScript: Open in Browser"** from the Command Palette to open
`http://localhost:5173` directly in your default browser instead.
