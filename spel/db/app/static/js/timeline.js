// Step timeline: x = routines in execution order (columns), one row per traced variable,
// marks = reads/writes, arcs = write -> next read, dashed arc = state carried into the next step.
(function () {
  const svg = document.getElementById("timeline");
  if (!svg) return;
  const wrap = document.getElementById("timeline-wrap");
  const tip = document.getElementById("tl-tooltip");
  const status = document.getElementById("tl-status");
  const allBox = document.getElementById("tl-all");
  const arcsBox = document.getElementById("tl-arcs");
  const LEFT = 210, TOP = 64, BOTTOM = 130, MINCOL = 26, MAXCOL = 90, MINROW = 48, MAXROW = 72;

  function url() {
    const p = new URLSearchParams(location.search);
    if (allBox && allBox.checked) p.set("all", "1");
    return svg.dataset.src + "?" + p.toString();
  }

  // read: hollow circle; write: solid square; read+write: solid diamond with a hollow core
  function markShape(g, s, r) {
    if (s === "r") g.append("circle").attr("r", r).attr("class", "mark mark-r");
    else if (s === "w") g.append("rect").attr("x", -r).attr("y", -r).attr("width", 2 * r).attr("height", 2 * r).attr("class", "mark mark-w");
    else {
      g.append("path").attr("d", `M0,${-r - 2} L${r + 2},0 L0,${r + 2} L${-r - 2},0 Z`).attr("class", "mark mark-rw");
      g.append("circle").attr("r", Math.max(2, r * 0.35)).attr("class", "mark-core");
    }
  }

  // Marks of one row that fall in the same column: spread across the column in
  // access order when they fit, else one merged glyph with a count.
  function placeMarks(marks, COL, msize) {
    const groups = new Map();
    marks.forEach((m, i) => { if (!groups.has(m.c)) groups.set(m.c, []); groups.get(m.c).push(i); });
    const placed = [];
    groups.forEach(idx => {
      const fit = Math.max(1, Math.floor((COL - 4) / (2 * msize + 2)));
      if (idx.length <= fit) {
        const step = idx.length > 1 ? Math.min(2 * msize + 2, (COL - 4) / idx.length) : 0;
        idx.forEach((i, k) => placed.push({ idx: [i], m: marks[i], dx: (k - (idx.length - 1) / 2) * step, s: marks[i].s, n: 1 }));
      } else {
        const ss = new Set(idx.map(i => marks[i].s));
        const s = ss.size === 1 ? [...ss][0] : "rw";
        placed.push({ idx, m: marks[idx[0]], dx: 0, s, n: idx.length, cond: idx.every(i => marks[i].cond) });
      }
    });
    return placed;
  }

  // shorten a label to fit `max` px (the full text stays in the title)
  function fitText(sel, max) {
    sel.each(function () {
      const t = d3.select(this); let text = t.text();
      while (text.length > 4 && this.getComputedTextLength() > max) { text = text.slice(0, -2) + "…"; t.text(text); }
    });
  }

  function arcPath(x1, x2, y, kind, rowH) {
    const h = Math.min(rowH * 0.42, 14 + Math.abs(x2 - x1) / 10);
    const up = kind === "next-read" ? -h : h;
    return `M${x1},${y + (up < 0 ? -9 : 9)} Q${(x1 + x2) / 2},${y + up * 1.5} ${x2},${y + (up < 0 ? -9 : 9)}`;
  }

  function draw(data) {
    const cols = data.columns, rows = data.rows;
    // spread few columns over the available width; many columns scroll horizontally
    const avail = Math.max(300, wrap.clientWidth - LEFT - 40);
    const COL = Math.max(MINCOL, Math.min(MAXCOL, Math.floor(avail / Math.max(cols.length, 1))));
    const ROW = Math.max(MINROW, Math.min(MAXROW, Math.floor(420 / Math.max(rows.length, 1))));
    const width = Math.max(wrap.clientWidth, LEFT + cols.length * COL + 40);
    const height = TOP + rows.length * ROW + BOTTOM;
    const root = d3.select(svg).attr("width", width).attr("height", height);
    root.selectAll("*").remove();
    if (!cols.length) {
      root.append("text").attr("x", LEFT).attr("y", TOP + 20).attr("class", "muted-text").text("No reachable accesses under this configuration.");
      status.textContent = "";
      return;
    }
    status.textContent = `${cols.length} routines · ${rows.reduce((n, r) => n + r.marks.length, 0)} accesses`;
    const x = i => LEFT + i * COL + COL / 2;
    const y = i => TOP + i * ROW + ROW / 2;
    const g = root.append("g");

    // step bands (elm_drv top-level calls)
    const bands = g.append("g").attr("class", "bands");
    data.steps.forEach((s, i) => {
      const x0 = LEFT + s.c0 * COL, x1 = LEFT + (s.c1 + 1) * COL;
      bands.append("rect").attr("x", x0).attr("y", TOP - 6).attr("width", x1 - x0).attr("height", rows.length * ROW + 12)
        .attr("class", "band" + (i % 2 ? " alt" : ""));
      const label = bands.append("text").attr("x", x0 + 3).attr("y", TOP - 14).attr("class", "band-label").text(s.label);
      if (x1 - x0 < s.label.length * 6.5) label.attr("transform", `rotate(-30, ${x0 + 3}, ${TOP - 14})`).attr("class", "band-label small");
    });

    // column labels
    const labels = g.append("g").attr("class", "col-labels");
    cols.forEach(c => {
      labels.append("text").attr("x", x(c.i)).attr("y", TOP + rows.length * ROW + 10)
        .attr("transform", `rotate(-60, ${x(c.i)}, ${TOP + rows.length * ROW + 10})`)
        .attr("class", "col-label").text(c.short).attr("data-sub", c.sub)
        .on("click", () => openDetails(c.sub, null));
      labels.append("line").attr("x1", x(c.i)).attr("x2", x(c.i)).attr("y1", TOP - 4).attr("y2", TOP + rows.length * ROW).attr("class", "col-guide").attr("data-col", c.i);
    });
    // hover a column: highlight its guide and label
    g.append("rect").attr("x", LEFT).attr("y", TOP).attr("width", cols.length * COL).attr("height", rows.length * ROW).attr("fill", "transparent")
      .on("mousemove", ev => {
        const [mx] = d3.pointer(ev, g.node());
        const ci = Math.floor((mx - LEFT) / COL);
        labels.selectAll(".col-guide").classed("hot", (d, i, nodes) => +nodes[i].getAttribute("data-col") === ci);
        labels.selectAll(".col-label").classed("hot", (d, i, nodes) => i === ci);
      }).on("mouseleave", () => { labels.selectAll(".hot").classed("hot", false); }).lower();

    rows.forEach((r, ri) => {
      const color = window.traceColor(ri);
      const rowG = g.append("g").attr("class", "trow");
      rowG.append("rect").attr("x", 0).attr("y", TOP + ri * ROW).attr("width", width).attr("height", ROW).attr("class", "row-bg" + (ri % 2 ? " alt" : ""))
        .attr("fill", color).attr("fill-opacity", ri % 2 ? 0.06 : 0.03);
      rowG.append("line").attr("x1", LEFT).attr("x2", LEFT + cols.length * COL).attr("y1", y(ri)).attr("y2", y(ri)).attr("class", "row-line").attr("stroke", color).attr("stroke-opacity", 0.35);
      const lab = rowG.append("text").attr("x", 8).attr("y", y(ri) - 3).attr("class", "row-label").attr("fill", color).text(r.label);
      fitText(lab, LEFT - 20);
      lab.append("title").text(`${r.key}: ${r.config_category} under this config (${r.category} overall)`);
      rowG.append("text").attr("x", 8).attr("y", y(ri) + 12).attr("class", "row-cat").text(r.config_category + (r.config_category !== r.category ? ` (${r.category} overall)` : ""));
      const msize = Math.max(5, Math.min(9, COL / 4));
      const placed = placeMarks(r.marks, COL, msize);
      const xOf = {}; placed.forEach(p => p.idx.forEach(i => { xOf[i] = x(p.m.c) + p.dx; }));
      if (arcsBox.checked) {
        r.arcs.forEach(a => {
          if (Math.abs(xOf[a.from] - xOf[a.to]) < 1) return; // within one merged glyph
          rowG.append("path").attr("d", arcPath(xOf[a.from], xOf[a.to], y(ri), a.kind, ROW))
            .attr("class", "arc arc-" + a.kind).attr("stroke", color);
        });
      }
      const marks = rowG.selectAll("g.m").data(placed).enter().append("g").attr("class", "m")
        .attr("transform", d => `translate(${x(d.m.c) + d.dx},${y(ri)})`).attr("fill", color).attr("stroke", color);
      marks.each(function (d) { markShape(d3.select(this), d.s, msize); }).classed("cond", d => d.n === 1 ? d.m.cond : d.cond);
      marks.filter(d => d.n > 1).append("text").attr("class", "mark-count").attr("x", msize + 3).attr("y", -msize + 2).text(d => `×${d.n}`);
      const what = s => s === "r" ? "read" : s === "w" ? "written" : "read+written";
      marks.on("mouseenter", (ev, d) => {
        const c = cols[d.m.c];
        if (d.n === 1) {
          tip.innerHTML = `<b>${r.label}</b> ${what(d.s)}<br>${c.sub} line ${d.m.ln + 1}<br><span class="muted">${c.top} · step position ${d.m.order}${d.m.from === "dummy" ? " · via argument" : ""}${d.m.cond ? " · inside an if block" : ""}</span>`;
        } else {
          const seq = d.idx.map(i => r.marks[i]).map(m => `${what(m.s)} at line ${m.ln + 1}${m.cond ? " (if)" : ""}`).join("<br>");
          tip.innerHTML = `<b>${r.label}</b> ${d.n} accesses in ${c.sub}<br><span class="muted">${c.top}</span><div class="dg-vars">${seq}</div>`;
        }
        tip.hidden = false;
        tip.style.left = (ev.pageX + 12) + "px"; tip.style.top = (ev.pageY - 10) + "px";
      }).on("mouseleave", () => { tip.hidden = true; })
        .on("click", (ev, d) => openDetails(cols[d.m.c].sub, d.m.ln));
    });
  }

  function openDetails(sub, ln) {
    const panel = document.getElementById("right-panel");
    if (!panel) return;
    const p = new URLSearchParams(location.search);
    const q = new URLSearchParams(); if (p.get("snap")) q.set("snap", p.get("snap")); if (p.get("cfg")) q.set("cfg", p.get("cfg"));
    if (ln !== null && ln !== undefined) q.set("ln", ln);
    htmx.ajax("GET", `/subroutine-details/${encodeURIComponent(sub)}/?${q}`, { target: "#right-panel", swap: "innerHTML" });
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function load() {
    if (!new URLSearchParams(location.search).getAll("v").length) { d3.select(svg).selectAll("*").remove(); status.textContent = ""; return; }
    status.textContent = "loading…";
    fetch(url(), { headers: { Accept: "application/json" } }).then(r => r.json()).then(draw)
      .catch(err => { status.textContent = "failed: " + err; });
  }
  allBox && allBox.addEventListener("change", load);
  arcsBox && arcsBox.addEventListener("change", load);
  svg.addEventListener("redraw", load);
  load();
})();
