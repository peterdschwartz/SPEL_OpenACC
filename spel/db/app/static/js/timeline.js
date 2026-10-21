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

  function markShape(sel, s, size) {
    const r = size || 7;
    sel.each(function (d) {
      const g = d3.select(this);
      if (s === "r") g.append("circle").attr("r", r).attr("class", "mark mark-r");
      else if (s === "w") g.append("rect").attr("x", -r).attr("y", -r).attr("width", 2 * r).attr("height", 2 * r).attr("class", "mark mark-w");
      else g.append("path").attr("d", `M0,${-r - 1} L${r + 1},0 L0,${r + 1} L${-r - 1},0 Z`).attr("class", "mark mark-rw");
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
      const lab = rowG.append("text").attr("x", 8).attr("y", y(ri) + 4).attr("class", "row-label").attr("fill", color).text(r.label);
      lab.append("title").text(`${r.key}: ${r.config_category} under this config (${r.category} overall)`);
      rowG.append("text").attr("x", LEFT - 6).attr("y", y(ri) + 4).attr("text-anchor", "end").attr("class", "row-cat").text(r.config_category);
      if (arcsBox.checked) {
        r.arcs.forEach(a => {
          const m1 = r.marks[a.from], m2 = r.marks[a.to];
          rowG.append("path").attr("d", arcPath(x(m1.c), x(m2.c), y(ri), a.kind, ROW))
            .attr("class", "arc arc-" + a.kind).attr("stroke", color);
        });
      }
      const marks = rowG.selectAll("g.m").data(r.marks).enter().append("g").attr("class", "m")
        .attr("transform", d => `translate(${x(d.c)},${y(ri)})`).attr("fill", color).attr("stroke", color);
      const msize = Math.max(6, Math.min(10, COL / 3));
      marks.each(function (d) { markShape(d3.select(this), d.s, msize); }).classed("cond", d => d.cond);
      marks.on("mouseenter", (ev, d) => {
        const c = cols[d.c];
        tip.innerHTML = `<b>${r.label}</b> ${d.s === "r" ? "read" : d.s === "w" ? "written" : "read+written"}<br>${c.sub} line ${d.ln + 1}<br><span class="muted">${c.top} · step position ${d.order}${d.from === "dummy" ? " · via argument" : ""}${d.cond ? " · inside an if block" : ""}</span>`;
        tip.hidden = false;
        tip.style.left = (ev.pageX + 12) + "px"; tip.style.top = (ev.pageY - 10) + "px";
      }).on("mouseleave", () => { tip.hidden = true; })
        .on("click", (ev, d) => openDetails(cols[d.c].sub, d.ln));
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
