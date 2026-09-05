// App — header (corpus name + counts + switcher), the three-column signal
// chain, and the prompt bar. specs/04_FRONTEND.md §2 "Layout" and
// "Corpus switcher".

import { useCallback, useEffect, useState } from "react";
import { API_BASE, useTaskStream, type FixtureName } from "./useTaskStream";
import { CorpusPanel } from "./panels/CorpusPanel";
import { CodePanel } from "./panels/CodePanel";
import { VerifierPanel } from "./panels/VerifierPanel";
import { PromptBar } from "./panels/PromptBar";
import { AddCorpusModal } from "./AddCorpusModal";

interface CorpusManifest {
  name: string;
  display_name: string;
  symbols: number;
  examples: number;
  pairs: number;
}

// Sentinel <option> value for the dropdown's onboarding entry — never a
// real corpus name, so it can never collide with one.
const ADD_CORPUS_OPTION = "__add_corpus__";

const FIXTURES: { name: FixtureName; label: string }[] = [
  { name: "immediate_pass", label: "immediate pass" },
  { name: "phase2_fail_then_repair", label: "fail then repair" },
  { name: "max_iterations_exhausted", label: "max iterations exhausted" },
];

// Dev-only fixture replay affordance: only reachable with ?fixtures=1 in a
// dev build, never the default path. specs/04_FRONTEND.md never says to
// build this UI — it's the harness build brief's own requirement for a
// replay mechanism, kept visually out of the way of the real interface.
const FIXTURES_ENABLED =
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search).get("fixtures") === "1";

export default function App() {
  const [corpora, setCorpora] = useState<CorpusManifest[]>([]);
  const [active, setActive] = useState<CorpusManifest | null>(null);
  const [addCorpusOpen, setAddCorpusOpen] = useState(false);
  const { state, running, start, startFixtureReplay, reset } = useTaskStream();

  useEffect(() => {
    fetch(`${API_BASE}/corpora`)
      .then((r) => r.json())
      .then((list: CorpusManifest[]) => {
        setCorpora(list);
        const preferred = list.find((c) => c.name === "plinth") ?? list[0];
        if (preferred) setActive(preferred);
      })
      .catch(() => {
        /* API not up yet — header renders the "offline" empty state below */
      });
  }, []);

  const handleSwitch = useCallback(
    async (name: string) => {
      const res = await fetch(`${API_BASE}/corpus/switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const manifest: CorpusManifest = await res.json();
      setActive(manifest);
      reset();
    },
    [reset],
  );

  const handleSubmit = useCallback(
    (prompt: string) => {
      if (!active) return;
      start(prompt, active.name);
    },
    [active, start],
  );

  const handleCorpusCreated = useCallback(
    (manifest: CorpusManifest, warnings: string[]) => {
      setCorpora((prev) => {
        const withoutDupe = prev.filter((c) => c.name !== manifest.name);
        return [...withoutDupe, manifest].sort((a, b) => a.name.localeCompare(b.name));
      });
      setActive(manifest);
      reset();
      setAddCorpusOpen(false);
      // Honest, not blocking: a corpus with a real toolchain but zero
      // retrieval material still works, it just retrieves badly. Surfaced
      // in the console rather than a dialog so it never interrupts the
      // "one click, visibly instant" switch this mirrors.
      for (const w of warnings) console.warn(`[corpus/create] ${manifest.name}: ${w}`);
    },
    [reset],
  );

  return (
    <div className="app">
      <header className="header">
        <span className="brand">Ashlar</span>
        <span className="manifest">
          {active
            ? `${active.display_name} · ${active.symbols} symbols · ${active.examples} examples · offline`
            : "connecting…"}
        </span>
        <div className="switcher">
          {corpora.length > 0 && (
            <select
              value={active?.name ?? ""}
              onChange={(e) => {
                if (e.target.value === ADD_CORPUS_OPTION) {
                  setAddCorpusOpen(true);
                  return;
                }
                handleSwitch(e.target.value);
              }}
              aria-label="switch corpus"
            >
              {corpora.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.display_name}
                </option>
              ))}
              <option value={ADD_CORPUS_OPTION}>+ add corpus</option>
            </select>
          )}
        </div>
      </header>

      <AddCorpusModal
        open={addCorpusOpen}
        onClose={() => setAddCorpusOpen(false)}
        onCreated={handleCorpusCreated}
      />

      {FIXTURES_ENABLED && (
        <div className="dev-fixture-note">
          dev fixture replay:{" "}
          {FIXTURES.map((f) => (
            <button
              key={f.name}
              onClick={() => startFixtureReplay(f.name)}
              style={{ marginRight: 8 }}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      <div className="columns">
        <CorpusPanel toolCalls={state.toolCalls} cacheHits={state.cacheHits} />
        <CodePanel code={state.code} errors={state.errors} verdict={state.verdict} />
        <VerifierPanel
          verdict={state.verdict}
          iteration={state.iteration}
          maxIter={state.maxIter}
          errors={state.errors}
          attempts={state.attempts}
          done={state.done}
          failedReason={state.failedReason}
          citations={state.citations}
          runOutput={state.runOutput}
        />
      </div>

      <PromptBar onSubmit={handleSubmit} running={running} />
    </div>
  );
}
