// Collapsible node-link view of the step tree (d3.tree, horizontal).
(function () {
  const svg = document.getElementById("calltree");
  if (!svg) return;
  const tip = document.getElementById("ct-tooltip");
  const wrap = document.getElementById("calltree-wrap");
  const subUrl = svg.dataset.subUrl;
  const ROWH = 22, COLW = 220;
  let root, gLinks, gNodes, zoomG;

  function url() {
    const p = new URLSearchParams(location.search);
    const r = document.getElementById("ct-root").value.trim(); if (r) p.set("root", r); else p.delete("root");
    p.set("depth", document.getElementById("ct-depth").value || 3);
    if (document.getElementById("ct-inactive").checked) p.set("inactive", "1");
    return svg.dataset.src + "?" + p.toString();
  }

  function toggle(d) {
    if (d.children) { d._children = d.children; d.children = null; }
    else if (d._children) { d.children = d._children; d._children = null; }
    else if (d.data.collapsed) { // children not loaded: fetch the subtree
      const p = new URLSearchParams(location.search); p.set("root", d.data.sub); p.set("depth", 2);
      if (document.getElementById("ct-inactive").checked) p.set("inactive", "1");
      fetch(svg.dataset.src + "?" + p.toString()).then(r => r.json()).then(j => {
        const sub = j.roots[0];
        d.data.children = sub.children || []; d.data.collapsed = 0;
        const h = d3.hierarchy(d.data);
        d.children = h.children; d.children && d.children.forEach(c => { c.parent = d; c.depth = d.depth + 1; });
        update();
      });
      return;
    }
    update();
  }

  function update() {
    const nodes = root.descendants(), links = root.links();
    const tree = d3.tree().nodeSize([ROWH, COLW]);
    tree(root);
    let y0 = Infinity, y1 = -Infinity;
    nodes.forEach(d => { if (d.x < y0) y0 = d.x; if (d.x > y1) y1 = d.x; });
    const height = Math.max(wrap.clientHeight, y1 - y0 + 60);
    d3.select(svg).attr("height", height);
    zoomG.attr("transform", `translate(40,${-y0 + 30})`);

    const link = gLinks.selectAll("path").data(links, d => d.target.data.id);
    link.exit().remove();
    link.enter().append("path").attr("class", "ct-link").merge(link)
      .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x))
      .classed("inactive", d => !d.target.data.active);

    const node = gNodes.selectAll("g.ct-node").data(nodes, d => d.data.id);
    node.exit().remove();
    const enter = node.enter().append("g").attr("class", "ct-node");
    enter.append("circle");
    enter.append("text").attr("dy", 4);
    enter.on("click", (ev, d) => toggle(d))
      .on("dblclick", (ev, d) => { ev.stopPropagation(); location.assign(subUrl.replace("X", encodeURIComponent(d.data.sub)) + location.search); })
      .on("mouseenter", (ev, d) => {
        tip.innerHTML = `<b>${d.data.label}</b><br>${d.data.size - 1} routines below · depth ${d.data.depth}${d.data.cut ? " · recursive call" : ""}${!d.data.analyzed ? " · not analyzed" : ""}${!d.data.active ? " · pruned by the config" : ""}` + (d.data.marks ? "<br>" + Object.entries(d.data.marks).map(([k, v]) => `${k}: ${v}`).join(", ") : "");
        tip.hidden = false; tip.style.left = (ev.pageX + 12) + "px"; tip.style.top = (ev.pageY - 10) + "px";
      }).on("mouseleave", () => { tip.hidden = true; });
    const all = enter.merge(node).attr("transform", d => `translate(${d.y},${d.x})`)
      .classed("inactive", d => !d.data.active).classed("unanalyzed", d => !d.data.analyzed).classed("cut", d => d.data.cut)
      .classed("collapsed", d => !!(d._children || d.data.collapsed));
    all.select("circle").attr("r", d => Math.min(12, 3 + Math.sqrt(d.data.size)));
    all.select("text").attr("x", d => (d.children ? -1 : 1) * (Math.min(12, 3 + Math.sqrt(d.data.size)) + 4)).attr("text-anchor", d => d.children ? "end" : "start")
      .text(d => d.data.name + (d.data.cut ? " ↺" : "") + ((d._children || d.data.collapsed) ? ` (+${d.data.collapsed || d.data.size - 1})` : ""));
  }

  function load() {
    fetch(url()).then(r => r.json()).then(j => {
      const sel = d3.select(svg).attr("width", Math.max(wrap.clientWidth, 1200));
      sel.selectAll("*").remove();
      zoomG = sel.append("g");
      gLinks = zoomG.append("g"); gNodes = zoomG.append("g");
      const data = j.roots.length === 1 ? j.roots[0] : { id: -1, name: "roots", label: "roots", size: 1, active: true, analyzed: true, children: j.roots };
      root = d3.hierarchy(data);
      sel.call(d3.zoom().scaleExtent([0.3, 3]).on("zoom", ev => { zoomG.attr("transform", ev.transform); }));
      update();
    });
  }
  document.getElementById("ct-reload").addEventListener("click", load);
  document.getElementById("ct-root").addEventListener("keydown", e => { if (e.key === "Enter") load(); });
  svg.addEventListener("redraw", load);
  load();
})();
