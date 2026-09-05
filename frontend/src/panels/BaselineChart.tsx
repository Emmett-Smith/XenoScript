// BaselineChart — three bars, values labeled directly, read from
// GET /eval/latest. specs/04_FRONTEND.md: "Never hardcode the numbers."
// The eval report format isn't nailed down by any spec here beyond
// "verified-correct rate per arm" (05_EVAL.md §3); no run had happened by
// the time this was built, so the server honestly returns
// {"error": "no report yet"}. This component reads whatever shape comes
// back defensively and renders the empty state truthfully rather than
// guessing at a schema or fabricating bars.

import { useEffect, useState } from "react";
import { API_BASE } from "../useTaskStream";

interface ArmRow {
  label: string;
  pct: number;
}

const ARM_LABELS: Record<string, string> = {
  A: "no tools, local model",
  D: "tools, local model",
  E: "tools, cloud model",
};

function extractRate(arm: unknown): number | null {
  if (typeof arm !== "object" || arm === null) return null;
  const a = arm as Record<string, unknown>;
  for (const key of [
    "verified_correct_rate",
    "verified_rate",
    "rate",
    "score",
  ]) {
    const v = a[key];
    if (typeof v === "number") return v <= 1 ? v * 100 : v;
  }
  return null;
}

export function BaselineChart() {
  const [rows, setRows] = useState<ArmRow[] | null>(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/eval/latest`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        if (!data || typeof data !== "object" || "error" in data) {
          setEmpty(true);
          return;
        }
        const arms = (data as Record<string, unknown>).arms;
        if (typeof arms !== "object" || arms === null) {
          setEmpty(true);
          return;
        }
        const out: ArmRow[] = [];
        for (const [key, label] of Object.entries(ARM_LABELS)) {
          const rate = extractRate((arms as Record<string, unknown>)[key]);
          if (rate !== null) out.push({ label, pct: rate });
        }
        if (out.length === 0) setEmpty(true);
        else setRows(out);
      })
      .catch(() => {
        if (!cancelled) setEmpty(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="baseline-chart">
      <h3>Baseline</h3>
      {empty || !rows ? (
        <div className="baseline-empty">no eval report yet</div>
      ) : (
        rows.map((row) => (
          <div className="baseline-row" key={row.label}>
            <span className="label">{row.label}</span>
            <span className="bar-track">
              <span
                className="bar-fill"
                style={{ width: `${Math.min(100, row.pct)}%` }}
              />
            </span>
            <span className="value">{Math.round(row.pct)}%</span>
          </div>
        ))
      )}
    </div>
  );
}
