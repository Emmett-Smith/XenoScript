// Timeline — the single chronological narrative of one task: retrieval,
// then each generate/verify/(repair) round in the order it actually
// happened, then real run output. Replaces the old three-always-visible-
// panels layout (Corpus | Generation | Verifier) with one scrolling
// transcript, the same shape a chat-style assistant uses: older steps
// collapse to a one-line summary once the run has moved past them, the
// step currently in progress (or the final, verified one) stays expanded.
// A step never disappears -- collapsing is the "it moved up" motion
// requested, not the removal of history.

import { useState } from "react";
import type { TimelineStep, VerifyError } from "../useTaskStream";
import { ToolCall } from "./CorpusPanel";
import { insertCodeIntoEditor, useVsCodeEmbed } from "../vscodeBridge";

function CodeBlock({ code, errors, streaming }: { code: string; errors: VerifyError[]; streaming: boolean }) {
  const errorsByLine = new Map<number, VerifyError>();
  for (const e of errors) if (!errorsByLine.has(e.line)) errorsByLine.set(e.line, e);
  const lines = code.length > 0 ? code.split("\n") : [];

  return (
    <div className="code-panel">
      {lines.map((line, i) => {
        const lineNo = i + 1;
        const err = errorsByLine.get(lineNo);
        return (
          <div className={`code-line${err ? " error-line" : ""}`} key={i}>
            <span className="gutter">{lineNo}</span>
            <span className="text">{line}</span>
            {err && <span className="badge">{err.code ?? "EHARNESS"}</span>}
          </div>
        );
      })}
      {streaming && (
        <div className="code-line">
          <span className="gutter" />
          <span className="text generating-cursor">▌</span>
        </div>
      )}
    </div>
  );
}

function attemptSummary(errors: VerifyError[], verified: boolean | null): string {
  if (verified === true) return "verified";
  if (verified === null) return "checking…";
  if (errors.length === 0) return "failed";
  const first = errors[0];
  const rest = errors.length > 1 ? ` (+${errors.length - 1} more)` : "";
  return `${first.code ?? "error"} line ${first.line}${rest}`;
}

// A glanceable state marker ahead of every step's summary -- filled dot
// while something is actively happening, check/cross once it lands.
// Plain characters, not an icon font: this has to render correctly
// inside a VS Code webview with no bundled assets and no network.
function StateMark({ state }: { state: "pending" | "ok" | "fail" }) {
  const glyph = state === "ok" ? "✓" : state === "fail" ? "✗" : "●";
  return <span className={`state-mark ${state}`}>{glyph}</span>;
}

function AttemptStep({
  step,
  expanded,
  onToggle,
  corpusExtension,
}: {
  step: Extract<TimelineStep, { kind: "attempt" }>;
  expanded: boolean;
  onToggle: () => void;
  corpusExtension?: string;
}) {
  const embeddedInVsCode = useVsCodeEmbed();
  const stateClass: "ok" | "fail" | "pending" =
    step.verified === true ? "ok" : step.verified === false ? "fail" : "pending";
  const label = step.streaming
    ? step.iteration === 1
      ? "Generating"
      : `Repairing (attempt ${step.iteration})`
    : step.iteration === 1
      ? "Attempt 1"
      : `Repair attempt ${step.iteration}`;
  const summary = step.streaming ? "writing…" : attemptSummary(step.errors, step.verified);

  if (!expanded) {
    return (
      <button type="button" className={`timeline-step collapsed ${stateClass}`} onClick={onToggle}>
        <span className="timeline-step-label">
          <StateMark state={stateClass} /> {label}
        </span>
        <span className="timeline-step-summary">{summary}</span>
      </button>
    );
  }

  return (
    <div className={`timeline-step expanded ${stateClass}`}>
      <button type="button" className="timeline-step-header" onClick={onToggle}>
        <span className="timeline-step-label">
          <StateMark state={stateClass} /> {label}
        </span>
        <span className="timeline-step-summary">{summary}</span>
      </button>
      <CodeBlock code={step.code} errors={step.errors} streaming={step.streaming} />
      {step.verified === false && step.errors.length > 0 && (
        <div className="current-error">
          <span className="code">{step.errors[0].code ?? "EHARNESS"}</span>
          <span className="loc">line {step.errors[0].line}</span>
          <div className="message">{step.errors[0].message}</div>
        </div>
      )}
      {step.verified === true && embeddedInVsCode && (
        <button
          type="button"
          className="insert-code-button"
          onClick={() => insertCodeIntoEditor(step.code, corpusExtension)}
        >
          Insert into editor
        </button>
      )}
    </div>
  );
}

function RetrievalStep({
  step,
  expanded,
  onToggle,
}: {
  step: Extract<TimelineStep, { kind: "retrieval" }>;
  expanded: boolean;
  onToggle: () => void;
}) {
  const totalHits = step.toolCalls.reduce((n, c) => n + (c.hits ?? 0), 0);
  const summary = step.cacheHit
    ? "cache hit"
    : step.toolCalls.length === 0
      ? "searching…"
      : `${step.toolCalls.length} lookups, ${totalHits} hits`;

  if (!expanded) {
    return (
      <button type="button" className="timeline-step collapsed" onClick={onToggle}>
        <span className="timeline-step-label">Corpus</span>
        <span className="timeline-step-summary">{summary}</span>
      </button>
    );
  }

  return (
    <div className="timeline-step expanded">
      <button type="button" className="timeline-step-header" onClick={onToggle}>
        <span className="timeline-step-label">Corpus</span>
        <span className="timeline-step-summary">{summary}</span>
      </button>
      {step.cacheHit && (
        <div className="tool-call">
          <div className="tool-name">Matched a previously verified answer</div>
          <div className="tool-args">cache key {step.cacheHit.slice(0, 10)}…</div>
        </div>
      )}
      {step.toolCalls.length === 0 && !step.cacheHit && (
        <div className="corpus-empty">no retrieval yet</div>
      )}
      {step.toolCalls.map((call, i) => (
        <ToolCall key={i} call={call} collapsed={false} />
      ))}
    </div>
  );
}

function RunOutputStep({ step }: { step: Extract<TimelineStep, { kind: "run_output" }> }) {
  const hasStdout = step.stdout.trim().length > 0;
  const hasStderr = step.stderr.trim().length > 0;
  const reason = !step.ok && step.errors[0]?.message;

  return (
    <div className="timeline-step expanded">
      <div className="timeline-step-header static">
        <span className="timeline-step-label">
          <StateMark state={step.ok ? "ok" : "fail"} /> Ran it
        </span>
      </div>
      <div className={`terminal-body ${step.ok ? "ok" : "fault"}`}>
        {hasStdout && <pre className="terminal-stdout">{step.stdout}</pre>}
        {hasStderr && <pre className={`terminal-stderr ${step.ok ? "ok" : "fault"}`}>{step.stderr}</pre>}
        {!hasStdout && !hasStderr && (
          <div className="terminal-empty">
            {reason || "Ran successfully, no output printed (expected for code that only stores data)"}
          </div>
        )}
      </div>
    </div>
  );
}

function FinalStep({ step }: { step: Extract<TimelineStep, { kind: "final" }> }) {
  return (
    <div className={`timeline-final ${step.ok ? "ok" : "fail"}`}>
      {step.ok ? "Verified." : `Stopped${step.reason ? ` — ${step.reason}` : ""}.`}
    </div>
  );
}

export function Timeline({
  prompt,
  timeline,
  corpusExtension,
}: {
  prompt: string | null;
  timeline: TimelineStep[];
  corpusExtension?: string;
}) {
  // Manual expand/collapse overrides, keyed by step index -- a click
  // always wins over the default-expanded computation below.
  const [overrides, setOverrides] = useState<Record<number, boolean>>({});
  const toggle = (i: number) =>
    setOverrides((prev) => ({ ...prev, [i]: !(prev[i] ?? defaultExpanded(i)) }));

  const lastAttemptIdx = [...timeline].map((s) => s.kind).lastIndexOf("attempt");
  const hasAttempts = lastAttemptIdx !== -1;

  function defaultExpanded(i: number): boolean {
    const step = timeline[i];
    if (step.kind === "retrieval") return !hasAttempts;
    if (step.kind === "attempt") return i === lastAttemptIdx;
    return true; // run_output steps default open; final is its own element
  }

  if (timeline.length === 0) {
    return <div className="timeline-empty">describe what you want written, below</div>;
  }

  return (
    <div className="timeline">
      {prompt && <div className="timeline-prompt">{prompt}</div>}
      {timeline.map((step, i) => {
        const expanded = overrides[i] ?? defaultExpanded(i);
        switch (step.kind) {
          case "retrieval":
            return <RetrievalStep key={i} step={step} expanded={expanded} onToggle={() => toggle(i)} />;
          case "attempt":
            return (
              <AttemptStep
                key={i}
                step={step}
                expanded={expanded}
                onToggle={() => toggle(i)}
                corpusExtension={corpusExtension}
              />
            );
          case "run_output":
            return <RunOutputStep key={i} step={step} />;
          case "final":
            return <FinalStep key={i} step={step} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
