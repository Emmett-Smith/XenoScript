// CodePanel — line numbers in --dim, streamed tokens appended directly (no
// typewriter simulation), error underline (2px --fault, not a background
// fill) + code badge on verify_result with errors, auto-scroll to the
// error line. specs/04_FRONTEND.md "Code panel specifics".

import { useEffect, useRef } from "react";
import type { VerdictState, VerifyError } from "../useTaskStream";
import { insertCodeIntoEditor, useVsCodeEmbed } from "../vscodeBridge";

export function CodePanel({
  code,
  errors,
  verdict,
  corpusExtension,
}: {
  code: string;
  errors: VerifyError[];
  verdict: VerdictState;
  corpusExtension?: string;
}) {
  const errorLineRef = useRef<HTMLDivElement | null>(null);
  const embeddedInVsCode = useVsCodeEmbed();
  const canInsert = embeddedInVsCode && verdict === "verified" && code.length > 0;

  const errorsByLine = new Map<number, VerifyError>();
  for (const e of errors) {
    if (!errorsByLine.has(e.line)) errorsByLine.set(e.line, e);
  }

  useEffect(() => {
    if (errors.length > 0 && errorLineRef.current) {
      errorLineRef.current.scrollIntoView({ block: "center" });
    }
  }, [errors]);

  const lines = code.length > 0 ? code.split("\n") : [];

  return (
    <div className="column code-column">
      <div className="column-header">
        <h2>Generation</h2>
        {canInsert && (
          <button
            type="button"
            className="insert-code-button"
            onClick={() => insertCodeIntoEditor(code, corpusExtension)}
          >
            Insert into editor
          </button>
        )}
      </div>
      <div className="code-panel">
        {lines.length === 0 && verdict === "idle" && (
          <div className="code-empty">no candidate yet</div>
        )}
        {lines.map((line, i) => {
          const lineNo = i + 1;
          const err = errorsByLine.get(lineNo);
          return (
            <div
              className={`code-line${err ? " error-line" : ""}`}
              key={i}
              ref={err ? errorLineRef : undefined}
            >
              <span className="gutter">{lineNo}</span>
              <span className="text">{line}</span>
              {err && <span className="badge">{err.code ?? "EHARNESS"}</span>}
            </div>
          );
        })}
        {verdict === "generating" && (
          <div className="code-line">
            <span className="gutter" />
            <span className="text generating-cursor">▌ generating…</span>
          </div>
        )}
      </div>
    </div>
  );
}
