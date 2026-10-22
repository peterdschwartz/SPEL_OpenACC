// Box diagram of one routine's callees (layered.js): rows = dependency depth, left->right = call order.
(function () {
  const svg = document.getElementById("calltree");
  if (!svg) return;
  const tip = document.getElementById("ct-tooltip"), wrap = document.getElementById("calltree-wrap"), crumbs = document.getElementById("ct-crumbs");
  const subUrl = svg.dataset.subUrl;
  const $ = id => document.getElementById(id);
  let trail = [], data = null;

  function url(root) {
    const p = new URLSearchParams(location.search);
    if (root) p.set("root", root); else p.delete("root");
    if ($("ct-inactive").checked) p.set("inactive", "1"); else p.delete("inactive");
    return svg.dataset.src + "?" + p.toString();
  }

  function draw() {
    if (!data) return;
    const showBook = $("ct-bookkeeping").checked;
    const shown = window.layeredGraph({
      svg, wrap, tip,
      nodes: data.nodes.filter(n => showBook || !n.bookkeeping), edges: data.edges,
      perRow: +$("ct-per-row").value || 5, allEdges: $("ct-all-edges").checked, hideIsolated: $("ct-hide-isolated").checked,
      name: d => d.name + (d.n > 1 ? ` (${d.k}/${d.n})` : ""),
      sub: d => (d.active ? "" : "pruned · ") + `${d.n_in} in · ${d.n_out} out` + (d.n_children ? ` · ${d.size - 1} below` : "") + (d.cut ? " ↺" : ""),
      nodeClass: d => (d.bookkeeping ? "book " : "") + (d.active ? "" : "inactive ") + (d.analyzed ? "" : "unanalyzed ") + (d.cut ? "cut " : "") + (d.n_children ? "expandable" : ""),
      nodeTip: d => `<b>${d.label}</b>${d.n > 1 ? `<br>call ${d.k} of ${d.n} under ${data.root.name}` : ""}<br>${d.n_in} inputs · ${d.n_out} outputs · ${d.size - 1} routines below` +
        (d.cut ? "<br>recursive call" : "") + (d.analyzed ? "" : "<br>not analyzed") + (d.active ? "" : "<br>pruned by the configuration") +
        (d.n_children ? "<br><i>click to open its callees, double-click for the routine page</i>" : "<br><i>double-click for the routine page</i>"),
      edgeTip: d => `<b>${d.s.name} → ${d.t.name}</b><br>${d.n} variable${d.n > 1 ? "s" : ""} written by the first and read by the second` +
        (d.n_excluded ? `<br>${d.n_excluded} more excluded: written and read under disjoint filters` : "") + (d.direct ? "" : "<br><i>implied by a chain of direct edges</i>") +
        `<div class="dg-vars">${d.vars.map(v => v.replace(/^.*::/, "")).join("<br>")}${d.n > d.vars.length ? "<br>…" : ""}</div>`,
      onClick: d => { if (d.n_children) load(d.sub, true); },
      onDblClick: d => location.assign(subUrl.replace("X", encodeURIComponent(d.sub)) + location.search),
    });
    $("ct-summary").textContent = `${shown.nodes.length} of ${data.nodes.length} callees of ${data.root.label}, ${shown.edges.length} edges, ${shown.rows} rows`;
  }

  function load(root, push) {
    fetch(url(root)).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(j => {
      if (push && data) trail.push({ sub: data.root.sub, name: data.root.name });
      data = j; $("ct-root").value = j.root.sub;
      window.crumbTrail(crumbs, trail, data.root.name, (c, i) => { trail = trail.slice(0, i); load(c.sub, false); });
      draw();
    }).catch(() => { $("ct-summary").textContent = `no routine named ${root}`; });
  }
  $("ct-reload").addEventListener("click", () => { trail = []; load($("ct-root").value.trim(), false); });
  $("ct-root").addEventListener("keydown", e => { if (e.key === "Enter") { trail = []; load(e.target.value.trim(), false); } });
  $("ct-root").addEventListener("pick", e => { trail = []; load(e.target.value.trim(), false); });
  $("ct-inactive").addEventListener("change", () => load($("ct-root").value.trim(), false));
  ["ct-per-row", "ct-all-edges", "ct-hide-isolated", "ct-bookkeeping"].forEach(id => $(id).addEventListener("change", draw));
  svg.addEventListener("redraw", () => load($("ct-root").value.trim(), false));
  load($("ct-root").value.trim(), false);
})();
