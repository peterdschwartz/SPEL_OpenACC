// Shared page behaviour: config/snapshot changes, source line focus, trace chips, highlighting.
(function () {
  const params = () => new URLSearchParams(location.search);

  function navigateWith(mutate) {
    const p = params();
    mutate(p);
    location.assign(location.pathname + (p.toString() ? "?" + p.toString() : ""));
  }

  // Snapshot/config pickers: reload partials, update the URL state when the page carries it.
  function onContextChanged(evt) {
    const detail = evt.detail || {};
    const p = params();
    if (evt.type === "configChanged" && p.has("cfg")) { navigateWith(q => q.set("cfg", detail.key)); return; }
    if (evt.type === "snapshotChanged" && p.has("snap")) { navigateWith(q => q.set("snap", detail.label)); return; }
    document.querySelectorAll("[data-reload-on-config]").forEach(el => htmx.trigger(el, "reload"));
    document.querySelectorAll("svg[data-src]").forEach(svg => svg.dispatchEvent(new CustomEvent("redraw")));
  }
  document.body.addEventListener("configChanged", onContextChanged);
  document.body.addEventListener("snapshotChanged", onContextChanged);

  // Suggestion dropdowns that fill an input (graph roots): set the value, close the list, tell the page.
  document.addEventListener("click", e => {
    const pick = e.target.closest("[data-pick-sub], [data-pick-mod]");
    if (!pick) return;
    e.preventDefault();
    const form = pick.closest(".search-form");
    const input = form && form.querySelector("input");
    if (!input) return;
    input.value = pick.dataset.pickSub || pick.dataset.pickMod;
    const res = form.querySelector(".search-results"); if (res) res.innerHTML = "";
    input.dispatchEvent(new CustomEvent("pick", { bubbles: true }));
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") document.querySelectorAll(".search-form .search-results").forEach(r => { r.innerHTML = ""; });
  });

  // Checkboxes that add a query parameter to a partial's request (e.g. show pruned routines).
  document.addEventListener("change", e => {
    const box = e.target.closest("input[data-param][data-target]");
    if (!box) return;
    const el = document.querySelector(box.dataset.target);
    if (!el) return;
    const url = new URL(el.getAttribute("hx-get"), location.origin);
    if (box.checked) url.searchParams.set(box.dataset.param, "1"); else url.searchParams.delete(box.dataset.param);
    el.setAttribute("hx-get", url.pathname + url.search);
    htmx.process(el);
    htmx.trigger(el, "reload");
  });

  // Source: jump to a line.
  function focusLine(ln) {
    const el = document.getElementById("L" + ln);
    if (!el) return;
    const src = el.closest("details");
    if (src && !src.open) src.open = true;
    document.querySelectorAll(".srcline.focus").forEach(x => x.classList.remove("focus"));
    el.classList.add("focus");
    el.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  document.addEventListener("click", e => {
    const a = e.target.closest("[data-goto-line]");
    if (!a) return;
    e.preventDefault();
    focusLine(a.dataset.gotoLine);
  });
  window.focusSourceLine = focusLine;

  // After swaps: highlight new code, focus a requested line, color chip swatches.
  function afterSwap(root) {
    root.querySelectorAll("code.language-fortran, pre code").forEach(block => { if (!block.dataset.highlighted) hljs.highlightElement(block); });
    const pane = root.querySelector ? root.querySelector("[data-focus-ln]") : null;
    if (pane && pane.dataset.focusLn) setTimeout(() => focusLine(pane.dataset.focusLn), 50);
  }
  document.body.addEventListener("htmx:afterSwap", e => afterSwap(e.target));
  document.addEventListener("DOMContentLoaded", () => {
    afterSwap(document);
    document.querySelectorAll("[data-swatch]").forEach(el => { el.style.setProperty("--swatch", window.traceColor ? window.traceColor(+el.dataset.swatch) : "#888"); });
  });

  // Palette shared with timeline.js (categorical, colorblind-friendly).
  const PALETTE = ["#1b6ec2", "#d9480f", "#2b8a3e", "#862e9c", "#0b7285", "#c92a2a", "#5f3dc4", "#e67700", "#087f5b", "#a61e4d"];
  window.traceColor = i => PALETTE[i % PALETTE.length];
})();
