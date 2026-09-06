// XenoScript pitch deck — keyboard/click navigation, speaker notes drawer.
// Press → / space to advance, ← to go back, N to toggle speaker notes,
// number keys 1-9 to jump. Notes never render in the main frame, so they
// stay out of any screen recording made of this window.

const slides = Array.from(document.querySelectorAll(".slide"));
const dotsWrap = document.getElementById("deckProgress");
const counter = document.getElementById("deckCounter");
const notesDrawer = document.getElementById("notesDrawer");
const notesBody = document.getElementById("notesBody");

let current = 0;
let notesOpen = false;

slides.forEach((_, i) => {
  const dot = document.createElement("div");
  dot.className = "dot";
  dot.addEventListener("click", () => goTo(i));
  dotsWrap.appendChild(dot);
});

function render() {
  slides.forEach((s, i) => {
    s.classList.remove("is-active", "is-prev");
    if (i === current) s.classList.add("is-active");
    else if (i < current) s.classList.add("is-prev");
  });
  Array.from(dotsWrap.children).forEach((d, i) => d.classList.toggle("is-active", i === current));
  counter.textContent = `${String(current + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")} — ${slides[current].dataset.title || ""}`;
  notesBody.textContent = slides[current].dataset.notes || "(no notes for this slide)";
}

function goTo(i) {
  current = Math.max(0, Math.min(slides.length - 1, i));
  render();
}

function next() { goTo(current + 1); }
function prev() { goTo(current - 1); }

document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") { e.preventDefault(); next(); }
  else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); prev(); }
  else if (e.key.toLowerCase() === "n") {
    notesOpen = !notesOpen;
    notesDrawer.classList.toggle("is-open", notesOpen);
  } else if (/^[1-9]$/.test(e.key)) {
    goTo(Number(e.key) - 1);
  }
});

document.addEventListener("click", (e) => {
  if (e.target.closest(".dot") || e.target.closest(".notes-drawer")) return;
  next();
});

render();
