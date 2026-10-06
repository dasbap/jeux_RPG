function mapPatterns(svg, element) {
  const defs = element("defs", {});
  const waterPattern = element("pattern", {id: "river-water", width: 40, height: 40, patternUnits: "userSpaceOnUse"});
  waterPattern.append(element("rect", {width: 40, height: 40, fill: "#285e70"}), element("path", {d: "M0 10 Q10 4 20 10 T40 10 M0 29 Q10 23 20 29 T40 29", fill: "none", stroke: "#61aabb", "stroke-width": 2, opacity: .6}));
  const bridgePattern = element("pattern", {id: "river-bridge", width: 40, height: 40, patternUnits: "userSpaceOnUse"});
  bridgePattern.append(element("rect", {width: 40, height: 40, fill: "#b39365"}), element("path", {d: "M0 8 H40 M0 19 H40 M0 30 H40 M4 0 V40 M36 0 V40", stroke: "#624a30", "stroke-width": 2, fill: "none"}));
  defs.append(waterPattern);
  for (const rotation of [0, 90, 180, 270]) {
    const pattern = bridgePattern.cloneNode(true);
    pattern.setAttribute("id", "river-bridge-" + rotation);
    pattern.setAttribute("patternTransform", "rotate(" + rotation + ")");
    defs.append(pattern);
  }
  svg.append(defs);
}
function decorateMap(svg, map, element, view, explored = null) {
  const {left, top, width, height} = view;
  for (const decoration of map.decorations || []) {
    const [x, y] = decoration.position;
    if (x < left || x >= left + width || y < top || y >= top + height || explored && !explored.has(`${x},${y}`)) continue;
    const group = element("g", {class: `terrain-decoration decor-${decoration.kind}`, "pointer-events": "none", transform: `translate(${x * 40},${y * 40})`});
    if (decoration.kind === "tree") {
      group.append(element("ellipse", {cx: 22, cy: 34, rx: 15, ry: 4, fill: "#102f23", opacity: .55}), element("rect", {x: 17, y: 17, width: 7, height: 18, fill: "#856342"}), element("circle", {cx: 13, cy: 17, r: 11, fill: "#335d3b"}), element("circle", {cx: 26, cy: 17, r: 12, fill: "#497e4d"}), element("circle", {cx: 20, cy: 10, r: 10, fill: "#76a867"}));
    } else if (decoration.kind === "house") {
      group.append(element("rect", {x: 4, y: 16, width: 32, height: 21, fill: "#c0a27b"}), element("path", {d: "M1 18 L20 2 L39 18 Z", fill: "#9a5645", stroke: "#5f3733", "stroke-width": 2}), element("rect", {x: 17, y: 25, width: 8, height: 12, fill: "#493d35"}));
    } else if (decoration.kind === "barricade") {
      group.append(element("path", {d: "M5 4L35 36M35 4L5 36M3 20H37", stroke: "#9a7048", "stroke-width": 6, "stroke-linecap": "round"}));
    } else if (decoration.kind === "wall") {
      group.append(element("rect", {x: 1, y: 4, width: 38, height: 32, fill: "#77808a", stroke: "#414950", "stroke-width": 2}), element("path", {d: "M1 15H39M1 26H39M13 4V15M27 15V26M13 26V36", stroke: "#424b54", "stroke-width": 2}));
    } else if (decoration.kind === "rock") {
      group.append(element("path", {d: "M3 29 L9 10 L26 5 L37 20 L32 34 L13 36 Z", fill: "#808a94", stroke: "#485561", "stroke-width": 2}), element("path", {d: "M9 10 L26 5 L23 20 L3 29 Z", fill: "#a8b1b5"}));
    } else {
      const icons = {flowers: "✿", grass: "⁙", crystal: "✦", camp: "▲"};
      group.append(element("text", {x: 20, y: 29, "text-anchor": "middle"}, icons[decoration.kind] || ""));
    }
    svg.append(group);
  }
}
function terrainCell(map, x, y, element, discovered = true, exit = false) {
  const has = field => (map[field] || []).some(p => p[0] === x && p[1] === y);
  const bridge = has("bridges");
  const rotation = (map.bridge_rotations || []).find(item => item.position[0] === x && item.position[1] === y)?.rotation || 0;
  const className = !discovered ? "battle-cell unexplored-cell" : exit ? "battle-cell battle-exit" : has("cover") ? "battle-cover" : bridge ? "battle-cell terrain-bridge" : has("water") ? "battle-cell terrain-water" : has("paths") ? "battle-cell terrain-path" : `battle-cell terrain-${map.biome || "forest"}${(x + y + (map.world_origin?.[0] || 0) + (map.world_origin?.[1] || 0)) % 2 ? " terrain-shade" : ""}`;
  const cell = element("rect", {x: x * 40, y: y * 40, width: 40, height: 40, class: className, role: "button", tabindex: "0", "data-cell": `${x},${y}`});
  if (bridge) {
    cell.setAttribute("data-rotation", rotation);
    if (discovered && !exit && !has("cover")) cell.classList.add(`bridge-rotation-${rotation}`);
  }
  return cell;
}
function renderStaticMap(map, markers = true) {
  const element = (tag, attrs, text = "") => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    node.textContent = text;
    return node;
  };
  const svg = element("svg", {viewBox: `0 0 ${map.width * 40} ${map.height * 40}`, class: "battle-map", role: "img", "aria-label": map.name});
  mapPatterns(svg, element);
  for (let y = 0; y < map.height; y++) for (let x = 0; x < map.width; x++) svg.append(terrainCell(map, x, y, element, true, markers && (map.exits || []).some(g => g.position[0] === x && g.position[1] === y)));
  decorateMap(svg, map, element, {left: 0, top: 0, width: map.width, height: map.height});
  if (markers) for (const [field, icon, className] of [["exits", "⇥", "exit-marker"], ["sites", "N", "field-site"], ["spawns", "G", "enemy-unit"]]) {
    for (const item of map[field] || []) {
      const point = Array.isArray(item) ? item : item.position;
      const group = element("g", {class: `battle-unit ${className}`});
      group.append(element("circle", {cx: point[0] * 40 + 20, cy: point[1] * 40 + 20, r: 13}), element("text", {x: point[0] * 40 + 20, y: point[1] * 40 + 25}, icon), element("title", {}, item.name || field));
      svg.append(group);
    }
  }
  return svg;
}
