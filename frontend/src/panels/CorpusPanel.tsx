// CorpusPanel — live tool calls, file:line results. specs/04_FRONTEND.md
// "Corpus panel specifics": this is the answer to "is it actually
// retrieving or just guessing." Never cut the live-calls feature; older
// calls collapse to one line so the panel doesn't overflow during a
// four-iteration run (cut-list item 2 — the one thing allowed to go if
// time runs out, not implemented here).

import type { ToolCallRecord } from "../useTaskStream";

export function previewLines(preview: unknown[]): string[] {
  const lines: string[] = [];
  for (const item of preview.slice(0, 3)) {
    const it = item as Record<string, unknown>;
    if (typeof it.file === "string" && typeof it.line === "number") {
      // grep_corpus hit
      lines.push(`${it.file}:${it.line}`);
    } else if (
      typeof it.file === "string" &&
      typeof it.start === "number" &&
      typeof it.end === "number"
    ) {
      // get_examples / read_file
      lines.push(`${it.file}:${it.start}-${it.end}`);
    } else if ("found" in it) {
      // lookup_symbol
      if (it.found) {
        const dim = (it.dimension as string | null) ?? (it.kind as string);
        const parents = Array.isArray(it.valid_parents)
          ? (it.valid_parents as string[])
          : [];
        lines.push(`${it.name} → ${dim}`);
        if (parents.length) lines.push(`→ ${parents.join(", ")}`);
      } else {
        lines.push(`${it.name} → not found`);
      }
    } else {
      lines.push(JSON.stringify(it).slice(0, 60));
    }
  }
  return lines;
}

export function ToolCall({
  call,
  collapsed,
}: {
  call: ToolCallRecord;
  collapsed: boolean;
}) {
  if (collapsed) {
    return (
      <div className="tool-call collapsed">
        <span className="tool-name">{call.tool}</span>
        <span>
          {call.hits !== undefined ? `${call.hits} hits` : "…"}
        </span>
      </div>
    );
  }
  const argEntries = Object.entries(call.args);
  const argSummary = argEntries
    .map(([k, v]) => (k === "pattern" || k === "name" || k === "symbol" || k === "path"
      ? String(v)
      : `${k}=${String(v)}`))
    .join(" ");
  return (
    <div className="tool-call">
      <div className="tool-name">{call.tool}</div>
      <div className="tool-args">"{argSummary}"</div>
      <div className="tool-count">
        {call.hits !== undefined ? `${call.hits} hits` : "waiting…"}
      </div>
      {call.preview &&
        previewLines(call.preview).map((line, i) => (
          <div className="tool-hit" key={i}>
            {line}
          </div>
        ))}
    </div>
  );
}

export function CorpusPanel({ toolCalls, cacheHits }: { toolCalls: ToolCallRecord[]; cacheHits: string[] }) {
  return (
    <div className="column corpus-panel">
      <h2>Corpus</h2>
      {toolCalls.length === 0 && cacheHits.length === 0 && (
        <div className="corpus-empty">no retrieval yet</div>
      )}
      {cacheHits.map((key, i) => (
        <div className="tool-call" key={`cache-${i}`}>
          <div className="tool-name">cache_hit</div>
          <div className="tool-args">"{key}"</div>
        </div>
      ))}
      {toolCalls.map((call, i) => (
        <ToolCall
          key={i}
          call={call}
          collapsed={i < toolCalls.length - 2}
        />
      ))}
    </div>
  );
}
