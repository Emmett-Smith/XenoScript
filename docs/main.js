// XenoScript marketing site — no framework, no build step.
// Three mechanisms: scroll progress rail, reveal-on-scroll, hero terminal
// typewriter, and a scrollytelling highlight for the "how it works" pipeline.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- scroll progress ----------
const progressFill = document.getElementById("progressFill");

function updateProgress() {
  const doc = document.documentElement;
  const scrolled = doc.scrollTop;
  const max = doc.scrollHeight - doc.clientHeight;
  const pct = max > 0 ? Math.min(100, (scrolled / max) * 100) : 0;
  progressFill.style.width = pct + "%";
  progressFill.classList.toggle("done", pct > 99);
}

document.addEventListener("scroll", () => requestAnimationFrame(updateProgress), { passive: true });
updateProgress();

// ---------- reveal on scroll ----------
const revealEls = document.querySelectorAll(".reveal");

if (reduceMotion) {
  revealEls.forEach((el) => el.classList.add("is-visible"));
} else {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
  );
  revealEls.forEach((el) => revealObserver.observe(el));
}

// ---------- hero terminal typewriter ----------
// Scripted against real project facts (the actual MUMPS add-patient demo
// pair, corpora/mumps/pairs/008) rather than a generic "AI writes code"
// mockup — matches the "corpus: mumps" label in the terminal chrome above.
const termBody = document.getElementById("termBody");

const SCRIPT = [
  { cls: "prompt-user", text: "> Store the string GARCIA,MARIA^45^F in the\n  uppercase global PATIENT under subscript 40,\n  then write it back out." },
  { cls: "tag-retrieve", text: "\n\n[retrieve] grep_corpus(\"SET ^PATIENT\") -> 5 hits\n[retrieve] get_examples(mumps) -> pairs/008" },
  { cls: "", text: "\n\n[generate] iteration 1/4 ..." },
  { cls: "tag-fault", text: "\n\n[verify]  rsm run candidate.m\n          FAIL — [Z12] Invalid expression, line 1" },
  { cls: "tag-repair", text: "\n\n[repair]  feeding real interpreter error back to model" },
  { cls: "", text: "\n[generate] iteration 2/4 ..." },
  { cls: "tag-verified", text: "\n\n[verify]  rsm run candidate.m\n          VERIFIED ✓  stdout: \"GARCIA,MARIA^45^F\"" },
];

async function typeScript() {
  termBody.innerHTML = "";
  for (const line of SCRIPT) {
    const span = document.createElement("span");
    if (line.cls) span.className = line.cls;
    termBody.appendChild(span);
    for (const ch of line.text) {
      span.textContent += ch;
      // Fast for whitespace/newlines, human-ish jitter for characters.
      const delay = ch === "\n" ? 90 : ch === " " ? 8 : 12 + Math.random() * 18;
      await sleep(delay);
    }
  }
  const caret = document.createElement("span");
  caret.className = "caret";
  termBody.appendChild(caret);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runTerminalLoop() {
  if (reduceMotion) {
    // Show the final, settled state without animating.
    termBody.innerHTML =
      '<span class="prompt-user">&gt; Store the string GARCIA,MARIA^45^F...</span>' +
      '<span class="tag-verified">\n\nVERIFIED ✓  stdout: "GARCIA,MARIA^45^F"</span>';
    return;
  }
  while (true) {
    await typeScript();
    await sleep(3200);
  }
}

runTerminalLoop();

// ---------- "how it works" scrollytelling ----------
const loopSteps = Array.from(document.querySelectorAll(".loop-step"));
const loopVisualCode = document.getElementById("loopVisualCode");

const VISUALS = [
  '&gt; grep_corpus("ELSE")\n4 hits &mdash; manual.md:88, pairs/004',
  '&gt; model drafts:\nKILL ^PATIENT(40)\nIF $DATA(^PATIENT(40))=0 WRITE "gone"',
  '&gt; rsm run candidate.m\n[Z13] Command syntax error, line 2',
  '&gt; repair turn, error fed back:\n"ELSE requires two spaces before its command"',
  '&gt; behavioral=1\nverified_cache: task hash 018e4feb… (citable)',
];

if (loopSteps.length) {
  const loopObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          loopSteps.forEach((s) => s.classList.remove("is-active"));
          entry.target.classList.add("is-active");
          const idx = Number(entry.target.dataset.step) || 0;
          loopVisualCode.innerHTML = VISUALS[idx] || VISUALS[0];
        }
      });
    },
    { threshold: 0.6, rootMargin: "-20% 0px -20% 0px" }
  );
  loopSteps.forEach((el) => loopObserver.observe(el));
  loopSteps[0].classList.add("is-active");
}

// ---------- eval bar chart: animate width once visible ----------
const barFills = document.querySelectorAll(".bar-fill");
const barObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const el = entry.target;
        el.style.width = el.dataset.w + "%";
        barObserver.unobserve(el);
      }
    });
  },
  { threshold: 0.4 }
);
barFills.forEach((el) => barObserver.observe(el));
