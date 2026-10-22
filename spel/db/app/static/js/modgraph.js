// Box diagram of the modules one module uses (or that use it), layered by their own use relations (layered.js).
(function () {
  const svg = document.getElementById("modgraph");
  if (!svg) return;
  const tip = document.getElementById("mg-tooltip"), wrap = document.getElementById("modgraph-wrap"), crumbs = document.getElementById("mg-crumbs");
  const modUrl = svg.dataset.modUrl;
  const $ = id => document.getElementById(id);
  let trail = [], data = null;

  function url(root) {
    const p = new URLSearchParams(location.search);
    if (root) p.set("root", root); else p.delete("root");
    p.set("dir", $("mg-dir").value);
    return svg.dataset.src + "?" + p.toString();
  }

  function draw() {
    if (!data) return;
    const minW = +$("mg-min").value || 1; $("mg-min-val").textContent = minW;
    const usedBy = data.dir === "usedby";
    const shown = window.layeredGraph({
      svg, wrap, tip,
      nodes: data.nodes, edges: data.edges.filter(e => e.n >= minW),
      perRow: +$("mg-per-row").value || 6, allEdges: $("mg-all-edges").checked, hideIsolated: $("mg-hide-isolated").checked,
      name: d => d.id,
      sub: d => `${d.subs} routines · ${d.globals} vars · ${d.n_uses} uses · used by ${d.n_used_by}`,
      nodeClass: d => (usedBy ? d.n_used_by : d.n_uses) ? "expandable" : "",
      nodeTip: d => `<b>${d.id}</b> <span class="muted">${d.file}</span><br>${d.subs} routines · ${d.globals} module variables<br>uses ${d.n_uses} modules · used by ${d.n_used_by}` +
        `<br><i>click to open what it ${usedBy ? "is used by" : "uses"}, double-click for the module page</i>`,
      edgeTip: d => `<b>${d.s.id}</b> uses <b>${d.t.id}</b>: ${d.whole ? "everything" : `${d.n} name${d.n > 1 ? "s" : ""}`}` +
        (d.direct ? "" : "<br><i>implied by a chain of direct edges</i>") + `<div class="dg-vars">${d.vars.join("<br>")}${d.n > d.vars.length ? "<br>…" : ""}</div>`,
      onClick: d => { if (usedBy ? d.n_used_by : d.n_uses) load(d.id, true); },
      onDblClick: d => location.assign(modUrl.replace("X", encodeURIComponent(d.id)) + location.search),
    });
    $("mg-summary").textContent = `${shown.nodes.length} of ${data.nodes.length} modules ${usedBy ? "using" : "used by"} ${data.root.id}, ${shown.edges.length} use edges among them, ${shown.rows} rows`;
  }

  function load(root, push) {
    fetch(url(root)).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(j => {
      if (push && data) trail.push({ id: data.root.id, name: data.root.id });
      data = j; $("mg-root").value = j.root.id;
      window.crumbTrail(crumbs, trail, data.root.id, (c, i) => { trail = trail.slice(0, i); load(c.id, false); });
      draw();
    }).catch(() => { $("mg-summary").textContent = `no module named ${root}`; });
  }
  $("mg-reload").addEventListener("click", () => { trail = []; load($("mg-root").value.trim(), false); });
  $("mg-root").addEventListener("keydown", e => { if (e.key === "Enter") { trail = []; load(e.target.value.trim(), false); } });
  $("mg-root").addEventListener("pick", e => { trail = []; load(e.target.value.trim(), false); });
  $("mg-dir").addEventListener("change", () => { trail = []; load($("mg-root").value.trim(), false); });
  ["mg-per-row", "mg-all-edges", "mg-hide-isolated", "mg-min"].forEach(id => $(id).addEventListener("input", draw));
  svg.addEventListener("redraw", () => load($("mg-root").value.trim(), false));
  load($("mg-root").value.trim(), false);
})();
