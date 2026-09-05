// TerminalPanel — real execution output of the verified candidate
// (run_output event). A clean parse only proves the code is well-formed;
// this is the part that proves it actually does something. Quiet until
// there's real output, same idle-state convention as the other panels
// (see CorpusPanel/CodePanel's "no retrieval yet"/"no candidate yet").

import type { VerifyError } from "../useTaskStream";

export interface RunOutput {
  stdout: string;
  stderr: string;
  ok: boolean;
  errors: VerifyError[];
}

export function TerminalPanel({ runOutput }: { runOutput: RunOutput | null }) {
  if (!runOutput) {
    return (
      <div className="terminal-panel">
        <h3>Output</h3>
        <div className="terminal-empty">no run yet</div>
      </div>
    );
  }

  const hasStdout = runOutput.stdout.trim().length > 0;
  const hasStderr = runOutput.stderr.trim().length > 0;
  // A compile-clean program can still have nothing to run (e.g. PLINTH's
  // "no scenario defined; nothing to run" for a bare platform block) --
  // that's a real, expected outcome, not a harness bug, so show why
  // rather than leaving a silent empty box next to a green "verified".
  const reason = !runOutput.ok && (runOutput.errors ?? [])[0]?.message;

  return (
    <div className="terminal-panel">
      <h3>Output</h3>
      <div className={`terminal-body ${runOutput.ok ? "ok" : "fault"}`}>
        {hasStdout && <pre className="terminal-stdout">{runOutput.stdout}</pre>}
        {hasStderr && <pre className="terminal-stderr">{runOutput.stderr}</pre>}
        {!hasStdout && !hasStderr && (
          <div className="terminal-empty">{reason || "(no stdout)"}</div>
        )}
      </div>
    </div>
  );
}
