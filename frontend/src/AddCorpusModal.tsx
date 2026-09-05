// AddCorpusModal — onboard a brand new corpus without leaving the SPA.
//
// The one thing this form must not imply: that uploading docs/examples
// alone is enough. verify()'s value depends entirely on a real,
// already-installed parser/compiler -- this form asks for the exact CLI
// commands to invoke one, exactly like meta.yaml's verifier block does
// today. Docs/examples are only the retrieval-seeding half of onboarding.
// Say that once, plainly, near the command fields -- no warning banner.

import { useState } from "react";
import { API_BASE } from "./useTaskStream";

interface CorpusManifest {
  name: string;
  display_name: string;
  extension: string;
  symbols: number;
  examples: number;
  pairs: number;
}

interface CreateResponse extends CorpusManifest {
  warnings?: string[];
}

export function AddCorpusModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (manifest: CorpusManifest, warnings: string[]) => void;
}) {
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [extension, setExtension] = useState("");
  const [commentPrefix, setCommentPrefix] = useState("#");
  const [parseCmd, setParseCmd] = useState("");
  const [runCmd, setRunCmd] = useState("");
  const [symbolsCmd, setSymbolsCmd] = useState("");
  const [outputFormat, setOutputFormat] = useState<"json" | "text">("json");
  const [errorRegex, setErrorRegex] = useState("");
  const [docs, setDocs] = useState<File[]>([]);
  const [examples, setExamples] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  function resetForm() {
    setName("");
    setDisplayName("");
    setExtension("");
    setCommentPrefix("#");
    setParseCmd("");
    setRunCmd("");
    setSymbolsCmd("");
    setOutputFormat("json");
    setErrorRegex("");
    setDocs([]);
    setExamples([]);
    setError(null);
  }

  function handleClose() {
    if (submitting) return;
    resetForm();
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const body = new FormData();
      body.append("name", name.trim());
      body.append("display_name", displayName.trim());
      body.append("extension", extension.trim());
      body.append("comment_prefix", commentPrefix);
      body.append("parse_cmd", parseCmd.trim());
      body.append("run_cmd", runCmd.trim());
      if (symbolsCmd.trim()) body.append("symbols_cmd", symbolsCmd.trim());
      body.append("output_format", outputFormat);
      if (outputFormat === "text") body.append("error_regex", errorRegex.trim());
      for (const f of docs) body.append("docs", f);
      for (const f of examples) body.append("examples", f);

      const res = await fetch(`${API_BASE}/corpus/create`, {
        method: "POST",
        body,
      });
      const payload = await res.json();
      if (!res.ok) {
        setError(payload.error ?? `request failed with status ${res.status}`);
        return;
      }
      const { warnings, ...manifest } = payload as CreateResponse;
      resetForm();
      onCreated(manifest, warnings ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Add corpus">
      <div className="modal-panel">
        <h2>Add corpus</h2>
        <form onSubmit={handleSubmit}>
          <div className="modal-row">
            <label>
              name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="mylang"
                required
              />
            </label>
            <label>
              display name
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="MyLang"
                required
              />
            </label>
          </div>
          <div className="modal-row">
            <label>
              extension
              <input
                value={extension}
                onChange={(e) => setExtension(e.target.value)}
                placeholder=".mylang"
                required
              />
            </label>
            <label>
              comment prefix
              <input
                value={commentPrefix}
                onChange={(e) => setCommentPrefix(e.target.value)}
                placeholder="#"
              />
            </label>
          </div>

          <p className="modal-note">
            These commands must already run on this machine. XenoScript does not install,
            detect, or guess a toolchain — it only runs exactly what you type here, the
            same way meta.yaml's verifier block works for every existing corpus.
          </p>

          <label className="modal-field-full">
            parse command (JSON array, <code className="mono">{"{file}"}</code> is substituted
            with the candidate's path)
            <input
              className="mono"
              value={parseCmd}
              onChange={(e) => setParseCmd(e.target.value)}
              placeholder='["mylang", "parse", "--json", "{file}"]'
              required
            />
          </label>
          <label className="modal-field-full">
            run command
            <input
              className="mono"
              value={runCmd}
              onChange={(e) => setRunCmd(e.target.value)}
              placeholder='["mylang", "run", "--json", "{file}"]'
              required
            />
          </label>
          <label className="modal-field-full">
            symbols command (optional)
            <input
              className="mono"
              value={symbolsCmd}
              onChange={(e) => setSymbolsCmd(e.target.value)}
              placeholder='["mylang", "symbols", "--json"]'
            />
          </label>

          <div className="modal-row modal-output-format">
            <span className="modal-toggle-label">output format</span>
            <label className="modal-radio">
              <input
                type="radio"
                name="output_format"
                checked={outputFormat === "json"}
                onChange={() => setOutputFormat("json")}
              />
              json
            </label>
            <label className="modal-radio">
              <input
                type="radio"
                name="output_format"
                checked={outputFormat === "text"}
                onChange={() => setOutputFormat("text")}
              />
              text
            </label>
          </div>

          {outputFormat === "text" && (
            <label className="modal-field-full">
              error regex (named groups: line required; file, col, severity, message optional)
              <input
                className="mono"
                value={errorRegex}
                onChange={(e) => setErrorRegex(e.target.value)}
                placeholder="^(?P<file>[^:]+):(?P<line>\d+): (?P<severity>\w+): (?P<message>.*)$"
                required
              />
            </label>
          )}

          <div className="modal-row">
            <label>
              docs
              <input
                type="file"
                multiple
                onChange={(e) => setDocs(Array.from(e.target.files ?? []))}
              />
            </label>
            <label>
              examples
              <input
                type="file"
                multiple
                onChange={(e) => setExamples(Array.from(e.target.files ?? []))}
              />
            </label>
          </div>

          {error && <p className="modal-error">{error}</p>}

          <div className="modal-actions">
            <button type="button" onClick={handleClose} disabled={submitting}>
              cancel
            </button>
            <button type="submit" disabled={submitting}>
              {submitting ? "creating…" : "create corpus"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
