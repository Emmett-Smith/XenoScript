// Bridge to the VS Code extension's webview host (vscode-extension/src/
// extension.ts), when this app is running inside that webview's <iframe>
// rather than a plain browser tab. Two jobs, matching the two message
// types the host script relays:
//
//   host -> here ("theme"): VS Code's live `--vscode-*` CSS variables,
//   applied to :root so styles.css's `[data-embed="vscode"]` rules can
//   pick them up. Re-sent by the host whenever the user switches themes.
//
//   here -> host ("insert-code"): ask the host to insert generated code
//   into the user's actual active editor. Only meaningful when embedded
//   -- calling it outside VS Code is a silent no-op, there is no editor
//   to insert into.
//
// A plain browser tab never receives a "theme" message, so `isEmbedded()`
// naturally stays false there and every VS Code-only affordance (the
// theme class, the "insert into editor" button) stays off.

import { useEffect, useState } from "react";

let embedded = false;
const embedListeners = new Set<(embedded: boolean) => void>();

function setEmbedded(value: boolean): void {
  if (embedded === value) return;
  embedded = value;
  for (const listener of embedListeners) listener(embedded);
}

export function isEmbeddedInVsCode(): boolean {
  return embedded;
}

export function onEmbedChange(listener: (embedded: boolean) => void): () => void {
  embedListeners.add(listener);
  return () => embedListeners.delete(listener);
}

function applyTheme(kind: string, vars: Record<string, string>): void {
  const root = document.documentElement;
  root.dataset.embed = "vscode";
  root.dataset.themeKind = kind;
  for (const [name, value] of Object.entries(vars)) {
    root.style.setProperty(name, value);
  }
}

export function initVsCodeBridge(): void {
  window.addEventListener("message", (event: MessageEvent) => {
    const data = event.data as { source?: string; type?: string; kind?: string; vars?: Record<string, string> };
    if (!data || data.source !== "ashlar-vscode-host") return;
    if (data.type === "theme") {
      setEmbedded(true);
      applyTheme(data.kind ?? "dark", data.vars ?? {});
    }
  });

  // Real bug found live: the host script only sent the theme on the
  // iframe's own `load` event, which can fire before this script has
  // even attached its listener (a fast/cached load beats the outer
  // script's own execution) -- the message goes out with nobody home to
  // receive it, and the panel is silently stuck on its default colors
  // until a live theme *switch* happens to trigger the host's fallback
  // MutationObserver. Fix: announce readiness ourselves and let the host
  // respond with the theme on its own schedule, not just once at its own
  // load time. Harmless outside VS Code -- nothing is listening.
  window.parent.postMessage({ source: "ashlar-webapp", type: "ready" }, "*");
}

/** Ask the VS Code extension host to insert `code` into the active editor
 * (at the cursor, or replacing the selection). `extension` is the active
 * corpus's real file extension (e.g. ".cbl"), used only as a best-effort
 * syntax-highlighting hint if there's no active editor to insert into
 * and a new file has to be opened. No-op outside VS Code. */
export function insertCodeIntoEditor(code: string, extension?: string): void {
  if (!embedded) return;
  window.parent.postMessage({ source: "ashlar-webapp", type: "insert-code", code, extension }, "*");
}

/** True once the VS Code host has confirmed itself (by sending a real
 * theme payload) -- false in a plain browser tab, always. */
export function useVsCodeEmbed(): boolean {
  const [value, setValue] = useState(embedded);
  useEffect(() => onEmbedChange(setValue), []);
  return value;
}
