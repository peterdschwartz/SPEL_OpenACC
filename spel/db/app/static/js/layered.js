// Layered box diagram shared by the tree graph and the module graph:
// rows = dependency depth (longest chain of edges above a node), left->right =
// the nodes' own order, wrapped at N per row; orthogonal edges routed through
// the channels between columns; levels and direct (transitively reduced) edges
// recomputed from the nodes on display.
(function () {
  const BOX_W = 190, BOX_H = 38, GAP_X = 56, GAP_Y = 64, PAD = 40;

  function layout(nodes, perRow) {
    const byLevel = new Map();
    nodes.forEach(n => { if (!byLevel.has(n.level)) byLevel.set(n.level, []); byLevel.get(n.level).push(n); });
    let row = 0, maxCols = 1;
    [...byLevel.keys()].sort((a, b) => a - b).forEach(l => {
      const group = byLevel.get(l).sort((a, b) => a.order - b.order);
      group.forEach((n, i) => { n.row = row + Math.floor(i / perRow); n.col = i % perRow; n.first = i === 0; });
      maxCols = Math.max(maxCols, Math.min(perRow, group.length));
      row += Math.ceil(group.length / perRow);
    });
    nodes.forEach(n => { n.x = PAD + n.col * (BOX_W + GAP_X); n.y = PAD + n.row * (BOX_H + GAP_Y); });
    return { rows: row, cols: maxCols };
  }

  function routeEdges(edges, nodes) {
    const occupied = new Set(nodes.map(n => `${n.row},${n.col}`));
    const chanX = c => PAD + c * (BOX_W + GAP_X) - GAP_X / 2;
    const byChannel = new Map();
    edges.forEach(e => {
      const s = e.s, t = e.t;
      let clear = s.col === t.col;
      for (let r = s.row + 1; clear && r < t.row; r++) if (occupied.has(`${r},${s.col}`)) clear = false;
      if (clear) { e.channel = null; return; }
      e.channel = t.col > s.col ? s.col + 1 : (t.col < s.col ? s.col : s.col + 1);
      if (!byChannel.has(e.channel)) byChannel.set(e.channel, []);
      byChannel.get(e.channel).push(e);
    });
    byChannel.forEach(list => {
      list.sort((a, b) => (a.t.row - b.t.row) || (a.s.row - b.s.row));
      const step = Math.min(7, (GAP_X - 14) / Math.max(1, list.length - 1));
      list.forEach((e, i) => { e.off = (i - (list.length - 1) / 2) * step; });
    });
    edges.forEach(e => {
      const x0 = e.s.x + BOX_W / 2, y0 = e.s.y + BOX_H, x1 = e.t.x + BOX_W / 2, y1 = e.t.y;
      if (e.channel === null) { e.path = `M${x0},${y0}L${x1},${y1}`; return; }
      const cx = chanX(e.channel) + e.off, ya = y0 + GAP_Y * 0.35 + e.off * 0.6, yb = y1 - GAP_Y * 0.35 + e.off * 0.6;
      e.path = `M${x0},${y0}L${x0},${ya}L${cx},${ya}L${cx},${yb}L${x1},${yb}L${x1},${y1}`;
    });
  }

  // Longest path above each node and transitive reduction, for any DAG order
  // (a cycle, which Fortran modules cannot have, just stops the relaxation).
  function levelsAndDirect(nodes, edges) {
    const idx = new Map(nodes.map((n, i) => [n.id, i]));
    const succ = nodes.map(() => new Set());
    edges.forEach(e => succ[idx.get(e.s.id)].add(idx.get(e.t.id)));
    const level = nodes.map(() => 0);
    for (let iter = 0, changed = true; changed && iter <= nodes.length; iter++) {
      changed = false;
      edges.forEach(e => { const a = idx.get(e.s.id), b = idx.get(e.t.id); if (level[b] < level[a] + 1) { level[b] = level[a] + 1; changed = true; } });
    }
    nodes.forEach((n, i) => { n.level = level[i]; });
    const down = nodes.map(() => null), visiting = new Set();
    const reach = i => {
      if (down[i]) return down[i];
      if (visiting.has(i)) return new Set();
      visiting.add(i);
      const acc = new Set();
      succ[i].forEach(j => { acc.add(j); reach(j).forEach(k => acc.add(k)); });
      visiting.delete(i); down[i] = acc; return acc;
    };
    edges.forEach(e => { const a = idx.get(e.s.id), b = idx.get(e.t.id); e.direct = ![...succ[a]].some(m => m !== b && reach(m).has(b)); });
  }

  function showTip(tip, ev, html) { tip.innerHTML = html; tip.hidden = false; tip.style.left = (ev.pageX + 12) + "px"; tip.style.top = (ev.pageY - 10) + "px"; }

  // opts: svg, wrap, tip, nodes, edges, perRow, allEdges, hideIsolated,
  //       name(d), sub(d), nodeClass(d), nodeTip(d), edgeTip(e), onClick(d), onDblClick(d)
  window.layeredGraph = function (opts) {
    const { svg, wrap, tip } = opts;
    let nodes = opts.nodes.slice();
    const byId = new Map(nodes.map(n => [n.id, n]));
    let edges = opts.edges.filter(e => byId.has(e.s) && byId.has(e.t)).map(e => ({ ...e, s: byId.get(e.s), t: byId.get(e.t) }));
    levelsAndDirect(nodes, edges);
    edges = edges.filter(e => opts.allEdges || e.direct);
    const connected = new Set(); edges.forEach(e => { connected.add(e.s.id); connected.add(e.t.id); });
    nodes = nodes.filter(n => !opts.hideIsolated || connected.has(n.id));
    const shown = new Set(nodes.map(n => n.id));
    edges = edges.filter(e => shown.has(e.s.id) && shown.has(e.t.id));
    const { rows, cols } = layout(nodes, Math.max(1, opts.perRow || 5));
    routeEdges(edges, nodes);
    const width = Math.max(wrap.clientWidth, PAD * 2 + cols * BOX_W + (cols - 1) * GAP_X);
    const height = Math.max(wrap.clientHeight, PAD * 2 + rows * (BOX_H + GAP_Y));

    const sel = d3.select(svg).attr("width", width).attr("height", height);
    sel.selectAll("*").remove();
    sel.append("defs").append("marker").attr("id", "dg-arrow").attr("viewBox", "0 -4 8 8").attr("refX", 8).attr("refY", 0)
      .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto").append("path").attr("d", "M0,-4L8,0L0,4").attr("class", "dg-arrow");
    const g = sel.append("g");
    sel.call(d3.zoom().scaleExtent([0.3, 3]).filter(ev => ev.type !== "wheel" || ev.ctrlKey).on("zoom", ev => g.attr("transform", ev.transform)));

    const link = g.append("g").selectAll("path").data(edges).enter().append("path")
      .attr("class", d => "dg-link" + (d.direct ? "" : " implied")).attr("d", d => d.path)
      .attr("stroke-width", d => 1 + Math.min(3, Math.log2(Math.max(1, d.n)) / 1.5))
      .attr("marker-end", "url(#dg-arrow)")
      .on("mouseenter", (ev, d) => showTip(tip, ev, opts.edgeTip(d)))
      .on("mouseleave", () => { tip.hidden = true; });

    const box = g.append("g").selectAll("g.dg-box").data(nodes).enter().append("g")
      .attr("class", d => "dg-box " + (opts.nodeClass ? opts.nodeClass(d) : ""))
      .attr("transform", d => `translate(${d.x},${d.y})`);
    box.append("rect").attr("width", BOX_W).attr("height", BOX_H).attr("rx", 6);
    box.append("text").attr("class", "dg-name").attr("x", 10).attr("y", 16)
      .text(d => { const t = opts.name(d); return t.length > 26 ? t.slice(0, 25) + "…" : t; });
    box.append("text").attr("class", "dg-sub").attr("x", 10).attr("y", 30).text(d => opts.sub(d));
    box.filter(d => /\bexpandable\b/.test(opts.nodeClass ? opts.nodeClass(d) : "")).append("text").attr("class", "dg-more").attr("x", BOX_W - 12).attr("y", 24).text("›");
    box.on("mouseenter", (ev, d) => {
      link.classed("hot", e => e.s === d || e.t === d).classed("dim", e => e.s !== d && e.t !== d);
      showTip(tip, ev, opts.nodeTip(d));
    }).on("mouseleave", () => { tip.hidden = true; link.classed("hot", false).classed("dim", false); })
      .on("click", (ev, d) => opts.onClick && opts.onClick(d))
      .on("dblclick", (ev, d) => { ev.stopPropagation(); opts.onDblClick && opts.onDblClick(d); });

    const levels = new Map(); nodes.forEach(n => { if (n.first) levels.set(n.level, n.y); });
    g.append("g").selectAll("line").data([...levels.entries()]).enter().append("line").attr("class", "dg-rule")
      .attr("x1", 4).attr("x2", width - 4).attr("y1", d => d[1] - GAP_Y / 2 + 4).attr("y2", d => d[1] - GAP_Y / 2 + 4).lower();
    return { nodes, edges, rows };
  };

  // breadcrumb trail of roots visited by clicking boxes
  window.crumbTrail = function (el, trail, current, go) {
    el.innerHTML = "";
    trail.forEach((c, i) => {
      const a = document.createElement("a"); a.href = "#"; a.textContent = c.name;
      a.onclick = ev => { ev.preventDefault(); go(c, i); };
      el.appendChild(a); el.appendChild(document.createTextNode(" › "));
    });
    const here = document.createElement("b"); here.textContent = current; el.appendChild(here);
  };
})();
