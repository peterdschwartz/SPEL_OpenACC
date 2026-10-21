// Force-directed module `use` graph.
(function () {
  const svg = document.getElementById("modgraph");
  if (!svg) return;
  const wrap = document.getElementById("modgraph-wrap");
  const tip = document.getElementById("mg-tooltip");
  const modUrl = svg.dataset.modUrl;
  const minInput = document.getElementById("mg-min"), minVal = document.getElementById("mg-min-val");
  const search = document.getElementById("mg-search"), labelsBox = document.getElementById("mg-labels");
  let data, sim;

  function draw() {
    const minW = +minInput.value; minVal.textContent = minW;
    const links = data.links.filter(l => l.weight >= minW).map(l => ({ ...l }));
    const linked = new Set(links.flatMap(l => [l.source, l.target]));
    const nodes = data.nodes.filter(n => linked.has(n.id)).map(n => ({ ...n }));
    const width = wrap.clientWidth, height = Math.max(600, wrap.clientHeight);
    const sel = d3.select(svg).attr("width", width).attr("height", height);
    sel.selectAll("*").remove();
    const g = sel.append("g");
    sel.call(d3.zoom().scaleExtent([0.2, 4]).on("zoom", ev => g.attr("transform", ev.transform)));
    sel.append("defs").append("marker").attr("id", "arrow").attr("viewBox", "0 -4 8 8").attr("refX", 12).attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
      .append("path").attr("d", "M0,-4L8,0L0,4").attr("class", "mg-arrow");
    const r = n => 4 + Math.sqrt(n.subs || 1) * 1.6;
    sim && sim.stop();
    sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(l => 60 + 40 / Math.sqrt(l.weight)).strength(l => Math.min(1, 0.2 + l.weight / 20)))
      .force("charge", d3.forceManyBody().strength(-180))
      .force("collide", d3.forceCollide(d => r(d) + 6))
      .force("center", d3.forceCenter(width / 2, height / 2));
    const link = g.append("g").selectAll("line").data(links).enter().append("line").attr("class", "mg-link")
      .attr("stroke-width", l => Math.min(6, 0.6 + Math.log2(l.weight))).attr("marker-end", "url(#arrow)");
    const node = g.append("g").selectAll("g").data(nodes).enter().append("g").attr("class", "mg-node")
      .call(d3.drag().on("start", (ev, d) => { d.fx = d.x; d.fy = d.y; }).on("drag", (ev, d) => { d.fx = ev.x; d.fy = ev.y; sim.alpha(0.3).restart(); }).on("end", (ev, d) => { d.fx = null; d.fy = null; }));
    node.append("circle").attr("r", r);
    node.append("text").attr("dx", d => r(d) + 3).attr("dy", 4).text(d => d.id).style("display", labelsBox.checked ? null : "none");
    node.on("mouseenter", (ev, d) => {
      const nb = new Set(links.filter(l => l.source.id === d.id || l.target.id === d.id).flatMap(l => [l.source.id, l.target.id]));
      node.classed("dim", n => !nb.has(n.id)); link.classed("dim", l => l.source.id !== d.id && l.target.id !== d.id);
      tip.innerHTML = `<b>${d.id}</b><br>${d.subs} routines · ${d.globals} module variables<br>uses ${links.filter(l => l.source.id === d.id).length} · used by ${links.filter(l => l.target.id === d.id).length}`;
      tip.hidden = false; tip.style.left = (ev.pageX + 12) + "px"; tip.style.top = (ev.pageY - 10) + "px";
    }).on("mouseleave", () => { node.classed("dim", false); link.classed("dim", false); tip.hidden = true; })
      .on("click", (ev, d) => location.assign(modUrl.replace("X", encodeURIComponent(d.id)) + location.search));
    sim.on("tick", () => {
      link.attr("x1", l => l.source.x).attr("y1", l => l.source.y).attr("x2", l => l.target.x).attr("y2", l => l.target.y);
      node.attr("transform", d => `translate(${d.x},${d.y})`);
    });
    search.oninput = () => { const q = search.value.toLowerCase(); node.classed("hit", d => q && d.id.includes(q)); };
    labelsBox.onchange = () => node.selectAll("text").style("display", labelsBox.checked ? null : "none");
  }
  function load() { fetch(svg.dataset.src + location.search).then(r => r.json()).then(j => { data = j; draw(); }); }
  minInput.addEventListener("input", draw);
  svg.addEventListener("redraw", load);
  load();
})();
