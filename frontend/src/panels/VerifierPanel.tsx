// VerifierPanel — the one bold element (the verdict block) plus the
// attempt ledger below it. specs/04_FRONTEND.md §2 state machine table:
// border + text + word change together, amber <-> green, nothing else in
// the UI uses either color. Ledger accumulates downward and persists
// after task_done/task_failed (never cleared here).

import type { AttemptRecord, Citation, VerdictState, VerifyError } from "../useTaskStream";
import { BaselineChart } from "./BaselineChart";
import { TerminalPanel } from "./TerminalPanel";

const WORD: Record<VerdictState, string> = {
  idle: "ready",
  generating: "generating",
  unverified: "unverified",
  repairing: "repairing",
  verified: "verified",
  failed: "not verified",
};

function attemptStatus(a: AttemptRecord): string {
  if (a.ok) return "verified";
  if (a.errors.length === 0) return "failed";
  const first = a.errors[0];
  const code = first.code ?? "EHARNESS";
  const rest = a.errors.length > 1 ? ` +${a.errors.length - 1} more` : "";
  return `${code} line ${first.line}${rest}`;
}

function CurrentError({ error }: { error: VerifyError }) {
  return (
    <div className="current-error">
      <span className="code">{error.code ?? "EHARNESS"}</span>
      <span className="loc">line {error.line}</span>
      <div className="message">{error.message}</div>
    </div>
  );
}

export function VerifierPanel({
  verdict,
  iteration,
  maxIter,
  errors,
  attempts,
  done,
  failedReason,
  citations,
  runOutput,
  corpusName,
}: {
  verdict: VerdictState;
  iteration: number;
  maxIter: number;
  errors: VerifyError[];
  attempts: AttemptRecord[];
  done: boolean;
  failedReason: string | null;
  citations: Citation[];
  runOutput: { stdout: string; stderr: string; ok: boolean; errors: VerifyError[] } | null;
  corpusName: string | null;
}) {
  const showCurrentError = errors.length > 0 && verdict !== "verified";

  return (
    <div className="column verifier-panel">
      <h2>Verifier</h2>
      <div className={`verdict-block state-${verdict}`}>
        <div className="word">{WORD[verdict]}</div>
        {verdict !== "idle" && (
          <div className="iter">
            iteration {iteration} / {maxIter}
          </div>
        )}
      </div>

      {showCurrentError && <CurrentError error={errors[0]} />}

      {attempts.length > 0 && (
        <div className="ledger">
          {attempts.map((a, i) => (
            <div className={`ledger-line ${a.ok ? "ok" : "fail"}`} key={i}>
              <span className="n">attempt {a.iteration}</span>
              <span className="status">{attemptStatus(a)}</span>
            </div>
          ))}
        </div>
      )}

      {done && verdict === "failed" && (
        <div className="failed-banner">
          task failed{failedReason ? ` — ${failedReason}` : ""}
        </div>
      )}

      {done && verdict === "verified" && citations.length > 0 && (
        <div className="failed-banner" style={{ color: "var(--dim)" }}>
          {citations.length} citation{citations.length === 1 ? "" : "s"}
        </div>
      )}

      <TerminalPanel runOutput={runOutput} />

      <BaselineChart corpusName={corpusName} />
    </div>
  );
}
