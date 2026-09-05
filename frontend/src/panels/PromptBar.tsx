// PromptBar — the task input. Visible keyboard focus states on both the
// input and the button are an explicit DoD item; handled by the
// :focus-visible rules in styles.css, not by anything special here.

import { useState } from "react";

export function PromptBar({
  onSubmit,
  running,
}: {
  onSubmit: (prompt: string) => void;
  running: boolean;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || running) return;
    onSubmit(trimmed);
  }

  return (
    <div className="prompt-bar">
      <span aria-hidden="true">▸</span>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
        }}
        placeholder="describe what you want written"
        disabled={running}
        aria-label="task prompt"
      />
      <button onClick={submit} disabled={running || value.trim().length === 0}>
        run
      </button>
    </div>
  );
}
