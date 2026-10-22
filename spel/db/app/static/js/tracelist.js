// The trace list: variables are collected (pending chips) and traced on demand with the Trace button.
// The traced list is the `v` query parameters; the pending list lives in sessionStorage so other pages can add to it.
(function () {
  const KEY = "tracelist";
  const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (e) { return []; } };
  const save = list => { try { sessionStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* private mode */ } };
  const traced = () => new URLSearchParams(location.search).getAll("v");
  const chipsEl = () => document.getElementById("chips");
  const onTracePage = () => chipsEl() !== null;
  let pending = load();

  function sameList(a, b) { return a.length === b.length && a.every((k, i) => k === b[i]); }

  function render() {
    const el = chipsEl();
    if (!el) return;
    const t = traced();
    const palette = i => (window.traceColor ? window.traceColor(i) : "#888");
    el.innerHTML = "";
    pending.forEach(item => {
      const ti = t.indexOf(item.key);
      const chip = document.createElement("span");
      chip.className = "chip" + (ti < 0 ? " pending" : "");
      chip.dataset.key = item.key;
      const sw = document.createElement("span"); sw.className = "chip-swatch"; sw.style.setProperty("--swatch", ti < 0 ? "#bbb" : palette(ti));
      chip.appendChild(sw);
      chip.appendChild(document.createTextNode(item.label || item.key));
      if (item.category) { const b = document.createElement("span"); b.className = "badge badge-cat-" + item.category; b.textContent = item.category; chip.appendChild(b); }
      const rm = document.createElement("a"); rm.href = "#"; rm.className = "chip-remove"; rm.dataset.removeVar = item.key; rm.title = "remove"; rm.textContent = "×";
      chip.appendChild(rm);
      el.appendChild(chip);
    });
    if (!pending.length) { const e = document.createElement("span"); e.className = "muted"; e.textContent = "No variables yet: pick some below."; el.appendChild(e); }
    const go = document.getElementById("trace-go");
    if (go) go.disabled = sameList(pending.map(p => p.key), t);
    const clear = document.getElementById("trace-clear");
    if (clear) clear.disabled = !pending.length;
    document.querySelectorAll("[data-add-var]").forEach(b => {
      const added = pending.some(p => p.key === b.dataset.addVar);
      b.classList.toggle("added", added);
      if (b.tagName === "BUTTON") { b.disabled = added; b.textContent = added ? "added" : "add"; }
    });
  }

  function toast(text, href) {
    document.querySelectorAll(".toast").forEach(x => x.remove());
    const t = document.createElement("div"); t.className = "toast";
    t.innerHTML = text + (href ? ` · <a href="${href}">open the trace</a>` : "");
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4500);
  }

  function add(key, label, category) {
    if (!key || pending.some(p => p.key === key)) return;
    pending.push({ key: key, label: label || key, category: category || "" });
    save(pending);
    if (onTracePage()) render();
    else { toast(`${label || key} added to the trace list (${pending.length})`, "/trace_view/"); render(); }
  }
  function remove(key) { pending = pending.filter(p => p.key !== key); save(pending); render(); }
  function clear() { pending = []; save(pending); render(); }

  function refreshViews() {
    const t = traced();
    const views = document.getElementById("trace-views"), intro = document.getElementById("trace-intro");
    if (views) views.hidden = !t.length;
    if (intro) intro.hidden = !!t.length;
    const panel = document.getElementById("left-panel");
    if (panel && t.length) htmx.ajax("GET", "/trace/?" + new URLSearchParams(location.search).toString(), { target: "#left-panel", swap: "innerHTML" });
    document.querySelectorAll("svg[data-src]").forEach(s => s.dispatchEvent(new CustomEvent("redraw")));
    render();
  }

  function trace() {
    const p = new URLSearchParams(location.search);
    p.delete("v");
    pending.forEach(x => p.append("v", x.key));
    history.pushState({}, "", location.pathname + "?" + p.toString());
    refreshViews();
  }

  document.addEventListener("click", e => {
    const add_ = e.target.closest("[data-add-var]");
    if (add_) { e.preventDefault(); add(add_.dataset.addVar, add_.dataset.label, add_.dataset.category); return; }
    const rm = e.target.closest("[data-remove-var]");
    if (rm) { e.preventDefault(); remove(rm.dataset.removeVar); return; }
    if (e.target.closest("#trace-go")) { e.preventDefault(); trace(); return; }
    if (e.target.closest("#trace-clear")) { e.preventDefault(); clear(); return; }
    const pick = e.target.closest("[data-pick-instance]");
    if (pick) {
      const field = document.getElementById("picker-instance");
      if (field) {
        e.preventDefault();
        field.value = pick.dataset.pickInstance;
        const filter = document.getElementById("picker-filter"); if (filter) filter.value = "";
        field.dispatchEvent(new Event("change", { bubbles: true }));
        const det = document.getElementById("picker"); if (det) det.open = true;
        if (filter) filter.focus();
      }
    }
  });
  window.addEventListener("popstate", () => { pending = traced().map(k => ({ key: k, label: k })); save(pending); refreshViews(); });
  document.body.addEventListener("htmx:afterSwap", () => render());
  document.addEventListener("DOMContentLoaded", () => {
    if (onTracePage()) {
      // chips rendered by the server (traced list) seed the pending list when it is empty
      const seeds = Array.from(document.querySelectorAll("#chips [data-seed-key]")).map(c => ({ key: c.dataset.seedKey, label: c.dataset.seedLabel, category: c.dataset.seedCategory }));
      traced().forEach(k => { if (!pending.some(p => p.key === k)) pending.push(seeds.find(s => s.key === k) || { key: k, label: k }); });
      seeds.forEach(s => { const p = pending.find(x => x.key === s.key); if (p) { p.label = s.label; p.category = s.category; } });
      save(pending);
      const views = document.getElementById("trace-views"), intro = document.getElementById("trace-intro");
      if (views) views.hidden = !traced().length;
      if (intro) intro.hidden = !!traced().length;
    }
    render();
  });
  window.TraceList = { add, remove, clear, trace, pending: () => pending.slice() };
})();
