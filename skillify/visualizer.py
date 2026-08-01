"""HTML visualizer for the skills knowledge graph.

Generates a self-contained HTML file with an interactive force-directed graph
visualization using D3.js v7. Features include search, category filtering,
zoom/pan, and a details panel for clicked nodes.
"""

import json
import os


def generate_html(graph_data: dict, output_dir: str) -> None:
    """Generate an interactive HTML visualization of the skills graph.

    Writes a self-contained graph.html file to output_dir with all CSS/JS
    inline and graph data embedded as a JavaScript variable.

    Args:
        graph_data: Graph dict with 'nodes', 'edges', and 'metadata' keys.
            - nodes: list of {id, label, category, keywords, description, path}
            - edges: list of {source, target, type, weight, shared}
            - metadata: {total_nodes, total_edges, categories, generated}
        output_dir: Directory where graph.html will be written.
    """
    os.makedirs(output_dir, exist_ok=True)

    graph_json = json.dumps(graph_data, ensure_ascii=False)
    # Escape </script> sequences to prevent breaking the HTML script block
    graph_json = graph_json.replace("</", "<\\/")

    html_content = _HTML_TEMPLATE.replace("__GRAPH_DATA__", graph_json)

    output_path = os.path.join(output_dir, "graph.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skillify — Skills Knowledge Graph</title>
<style>
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: #0a0c0f;
    color: #e8eaf0;
    overflow: hidden;
    height: 100vh;
    width: 100vw;
}

#app {
    display: flex;
    flex-direction: column;
    height: 100vh;
}

header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    background: #111417;
    border-bottom: 1px solid rgba(0, 229, 180, 0.22);
    flex-shrink: 0;
    z-index: 10;
}

header h1 {
    font-size: 1.2rem;
    font-weight: 600;
    color: #00e5b4;
    letter-spacing: 0.5px;
}

.stats-bar {
    font-size: 0.85rem;
    color: #a7aebd;
}

.main-container {
    display: flex;
    flex: 1;
    overflow: hidden;
    position: relative;
}

.sidebar {
    width: 280px;
    background: #111417;
    border-right: 1px solid rgba(0, 229, 180, 0.15);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    flex-shrink: 0;
    z-index: 5;
}

.sidebar-section {
    padding: 14px 16px;
    border-bottom: 1px solid rgba(0, 229, 180, 0.1);
}

.sidebar-section h3 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #00e5b4;
    margin-bottom: 10px;
}

.search-input {
    width: 100%;
    padding: 8px 12px;
    background: #161b22;
    border: 1px solid rgba(0, 229, 180, 0.3);
    border-radius: 6px;
    color: #e8eaf0;
    font-size: 0.85rem;
    outline: none;
    transition: border-color 0.2s;
}

.search-input:focus {
    border-color: #00e5b4;
}

.search-input::placeholder {
    color: #606876;
}

.category-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 300px;
    overflow-y: auto;
}

.category-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    cursor: pointer;
    padding: 4px 0;
}

.category-item input[type="checkbox"] {
    accent-color: #00e5b4;
    cursor: pointer;
}

.category-color {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.category-label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

#graph-container {
    flex: 1;
    position: relative;
    overflow: hidden;
}

#graph-container svg {
    width: 100%;
    height: 100%;
    display: block;
}

.info-panel {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 340px;
    max-height: 50%;
    background: #111417;
    border-top: 1px solid rgba(0, 229, 180, 0.22);
    border-left: 1px solid rgba(0, 229, 180, 0.22);
    border-top-left-radius: 12px;
    padding: 18px;
    overflow-y: auto;
    display: none;
    z-index: 10;
    box-shadow: -4px -4px 20px rgba(0, 0, 0, 0.4);
}

.info-panel.visible {
    display: block;
}

.info-panel .close-btn {
    position: absolute;
    top: 10px;
    right: 14px;
    background: none;
    border: none;
    color: #7a9a90;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 4px;
}

.info-panel .close-btn:hover {
    color: #00e5b4;
}

.info-panel h2 {
    font-size: 1rem;
    color: #00e5b4;
    margin-bottom: 8px;
    padding-right: 24px;
}

.info-panel .info-field {
    margin-bottom: 10px;
}

.info-panel .info-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #606876;
    margin-bottom: 3px;
}

.info-panel .info-value {
    font-size: 0.85rem;
    color: #c2c8d2;
    line-height: 1.4;
}

.info-panel .info-value.path {
    font-family: "SFMono-Regular", "Roboto Mono", Consolas, monospace;
    font-size: 0.78rem;
    color: #a7aebd;
    word-break: break-all;
}

.info-panel .keyword-tag {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(0, 229, 180, 0.08);
    border: 1px solid rgba(0, 229, 180, 0.22);
    border-radius: 4px;
    font-size: 0.75rem;
    margin: 2px 4px 2px 0;
    color: #00e5b4;
}

.info-panel .connection-item {
    padding: 4px 0;
    font-size: 0.82rem;
    color: #b0c8c0;
    cursor: pointer;
}

.info-panel .connection-item:hover {
    color: #00e5b4;
}

.tooltip {
    position: absolute;
    background: #161b22;
    border: 1px solid rgba(0, 229, 180, 0.3);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.78rem;
    color: #e8eaf0;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    z-index: 100;
    white-space: nowrap;
}

.tooltip.visible {
    opacity: 1;
}

.node-highlighted {
    stroke: #fff !important;
    stroke-width: 3px !important;
}

@media (max-width: 768px) {
    .sidebar {
        width: 220px;
    }
    .info-panel {
        width: 100%;
        border-left: none;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }
}

@media (max-width: 480px) {
    .main-container {
        flex-direction: column;
    }
    .sidebar {
        width: 100%;
        max-height: 140px;
        border-right: none;
        border-bottom: 1px solid rgba(0, 212, 170, 0.15);
    }
}
</style>
</head>
<body>
<div id="app">
    <header>
        <h1>Skillify &mdash; Skills Knowledge Graph</h1>
        <div class="stats-bar" id="stats-bar"></div>
    </header>
    <div class="main-container">
        <aside class="sidebar">
            <div class="sidebar-section">
                <h3>Search</h3>
                <input type="text" class="search-input" id="search-input" placeholder="Search skills..." aria-label="Search skills">
            </div>
            <div class="sidebar-section">
                <h3>Categories</h3>
                <div class="category-list" id="category-list"></div>
            </div>
        </aside>
        <div id="graph-container">
            <div class="tooltip" id="tooltip"></div>
            <div class="info-panel" id="info-panel">
                <button class="close-btn" id="close-panel" aria-label="Close details panel">&times;</button>
                <div id="panel-content"></div>
            </div>
        </div>
    </div>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
(function() {
    "use strict";

    const graphData = __GRAPH_DATA__;

    const nodes = graphData.nodes || [];
    const edges = graphData.edges || [];
    const metadata = graphData.metadata || {};
    const categories = metadata.categories || [];

    // Stats
    document.getElementById("stats-bar").textContent =
        `${nodes.length} skills \\u00B7 ${edges.length} connections \\u00B7 ${categories.length} categories`;

    // Color palette for categories
    const categoryColors = {};
    const palette = [
        "#00e5b4", "#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4",
        "#0984e3", "#74b9ff", "#a29bfe", "#6c5ce7", "#fd79a8",
        "#e17055", "#fdcb6e", "#ffeaa7", "#fab1a0", "#dfe6e9",
        "#00b4d8", "#48cae4", "#90e0ef", "#2ec4b6", "#cbf3f0"
    ];
    categories.forEach((cat, i) => {
        categoryColors[cat] = palette[i % palette.length];
    });

    // Compute degree for node sizing
    const degreeMap = {};
    nodes.forEach(n => { degreeMap[n.id] = 0; });
    edges.forEach(e => {
        const src = typeof e.source === "object" ? e.source.id : e.source;
        const tgt = typeof e.target === "object" ? e.target.id : e.target;
        if (degreeMap[src] !== undefined) degreeMap[src]++;
        if (degreeMap[tgt] !== undefined) degreeMap[tgt]++;
    });

    // Build adjacency for info panel
    const adjacency = {};
    nodes.forEach(n => { adjacency[n.id] = []; });
    edges.forEach(e => {
        const src = typeof e.source === "object" ? e.source.id : e.source;
        const tgt = typeof e.target === "object" ? e.target.id : e.target;
        adjacency[src]?.push({ id: tgt, type: e.type, weight: e.weight });
        adjacency[tgt]?.push({ id: src, type: e.type, weight: e.weight });
    });

    // Node ID to node lookup
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.id] = n; });

    // Category filters
    const activeCategories = new Set(categories);
    const categoryListEl = document.getElementById("category-list");
    categories.forEach(cat => {
        const item = document.createElement("label");
        item.className = "category-item";
        item.innerHTML = `
            <input type="checkbox" checked data-category="${cat}">
            <span class="category-color" style="background:${categoryColors[cat]}"></span>
            <span class="category-label">${cat}</span>
        `;
        categoryListEl.appendChild(item);
        item.querySelector("input").addEventListener("change", (ev) => {
            if (ev.target.checked) {
                activeCategories.add(cat);
            } else {
                activeCategories.delete(cat);
            }
            updateVisibility();
        });
    });

    // D3 setup
    const container = document.getElementById("graph-container");
    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select("#graph-container")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    const g = svg.append("g");

    // Zoom
    const zoom = d3.zoom()
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
            currentZoom = event.transform.k;
            updateLabels();
        });
    svg.call(zoom);

    let currentZoom = 1;

    // Edge color by type
    function edgeColor(type) {
        return type === "keyword" ? "rgba(0, 229, 180, 0.35)" : "rgba(0, 229, 180, 0.2)";
    }

    // Simulation
    const simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(edges).id(d => d.id).distance(80))
        .force("charge", d3.forceManyBody().strength(-120))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(d => nodeRadius(d) + 2));

    // Draw edges
    const linkGroup = g.append("g").attr("class", "links");
    const link = linkGroup.selectAll("line")
        .data(edges)
        .join("line")
        .attr("stroke", d => edgeColor(d.type))
        .attr("stroke-width", d => Math.max(0.5, d.weight * 0.8))
        .attr("stroke-opacity", 0.6);

    // Draw nodes
    function nodeRadius(d) {
        const degree = degreeMap[d.id] || 0;
        return Math.max(5, Math.min(20, 5 + degree * 1.5));
    }

    const nodeGroup = g.append("g").attr("class", "nodes");
    const node = nodeGroup.selectAll("circle")
        .data(nodes)
        .join("circle")
        .attr("r", d => nodeRadius(d))
        .attr("fill", d => categoryColors[d.category] || "#00e5b4")
        .attr("stroke", "#0a0c0f")
        .attr("stroke-width", 1.5)
        .attr("cursor", "pointer")
        .call(d3.drag()
            .on("start", dragStarted)
            .on("drag", dragged)
            .on("end", dragEnded));

    // Labels — always visible (like Obsidian graph)
    const labelGroup = g.append("g").attr("class", "labels");
    const labels = labelGroup.selectAll("text")
        .data(nodes)
        .join("text")
        .text(d => d.label)
        .attr("font-size", "10px")
        .attr("fill", "#c2c8d2")
        .attr("text-anchor", "middle")
        .attr("dy", d => -(nodeRadius(d) + 4))
        .attr("pointer-events", "none")
        .style("opacity", 0.85);

    function updateLabels() {
        // Labels always shown; no zoom gating
    }

    // Tooltip (only for extra detail on hover)
    const tooltip = document.getElementById("tooltip");

    node.on("mouseenter", (event, d) => {
        tooltip.textContent = d.label + (d.category ? " [" + d.category + "]" : "");
        tooltip.classList.add("visible");
        const rect = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - rect.left + 12) + "px";
        tooltip.style.top = (event.clientY - rect.top - 10) + "px";
    })
    .on("mousemove", (event) => {
        const rect = container.getBoundingClientRect();
        tooltip.style.left = (event.clientX - rect.left + 12) + "px";
        tooltip.style.top = (event.clientY - rect.top - 10) + "px";
    })
    .on("mouseleave", () => {
        tooltip.classList.remove("visible");
    })
    .on("click", (event, d) => {
        event.stopPropagation();
        showInfoPanel(d);
    });

    // Click on background to close panel
    svg.on("click", () => {
        hideInfoPanel();
    });

    // Simulation tick
    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
        node
            .attr("cx", d => d.x)
            .attr("cy", d => d.y);
        labels
            .attr("x", d => d.x)
            .attr("y", d => d.y);
    });

    // Drag behavior
    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    // Search
    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim().toLowerCase();
        if (!query) {
            node.attr("opacity", 1).classed("node-highlighted", false);
            link.attr("opacity", 0.6);
            labels.style("opacity", 0.85);
            return;
        }
        node.each(function(d) {
            const match = d.label.toLowerCase().includes(query) ||
                d.category.toLowerCase().includes(query) ||
                (d.keywords || []).some(k => k.toLowerCase().includes(query));
            d3.select(this)
                .attr("opacity", match ? 1 : 0.15)
                .classed("node-highlighted", match);
        });
        link.attr("opacity", 0.1);
        labels.style("opacity", function(d) {
            const match = d.label.toLowerCase().includes(query) ||
                d.category.toLowerCase().includes(query) ||
                (d.keywords || []).some(k => k.toLowerCase().includes(query));
            return match ? 1 : 0.1;
        });
    });

    // Category filter visibility
    function updateVisibility() {
        node.style("display", d => activeCategories.has(d.category) ? null : "none");
        labels.style("display", d => activeCategories.has(d.category) ? null : "none");
        link.style("display", d => {
            const srcCat = (typeof d.source === "object" ? d.source : nodeMap[d.source])?.category;
            const tgtCat = (typeof d.target === "object" ? d.target : nodeMap[d.target])?.category;
            return activeCategories.has(srcCat) && activeCategories.has(tgtCat) ? null : "none";
        });
    }

    // Info panel
    const infoPanel = document.getElementById("info-panel");
    const panelContent = document.getElementById("panel-content");
    document.getElementById("close-panel").addEventListener("click", hideInfoPanel);

    function showInfoPanel(d) {
        const connections = adjacency[d.id] || [];
        const connHtml = connections.map(c => {
            const n = nodeMap[c.id];
            const label = n ? n.label : c.id;
            return `<div class="connection-item" data-id="${c.id}">${label} <span style="color:#5a7a70;font-size:0.72rem">(${c.type}, w:${c.weight})</span></div>`;
        }).join("");

        const keywordsHtml = (d.keywords || [])
            .map(k => `<span class="keyword-tag">${k}</span>`).join("");

        panelContent.innerHTML = `
            <h2>${d.label}</h2>
            <div class="info-field">
                <div class="info-label">Category</div>
                <div class="info-value"><span class="keyword-tag" style="border-color:${categoryColors[d.category]};color:${categoryColors[d.category]}">${d.category}</span></div>
            </div>
            ${d.description ? `<div class="info-field"><div class="info-label">Description</div><div class="info-value">${d.description}</div></div>` : ""}
            ${d.keywords?.length ? `<div class="info-field"><div class="info-label">Keywords</div><div class="info-value">${keywordsHtml}</div></div>` : ""}
            ${d.path ? `<div class="info-field"><div class="info-label">Path</div><div class="info-value path">${d.path}</div></div>` : ""}
            <div class="info-field">
                <div class="info-label">Connections (${connections.length})</div>
                <div class="info-value">${connHtml || "<em style=\\"color:#5a7a70\\">No connections</em>"}</div>
            </div>
        `;
        infoPanel.classList.add("visible");

        // Clickable connections
        panelContent.querySelectorAll(".connection-item").forEach(el => {
            el.addEventListener("click", () => {
                const targetNode = nodeMap[el.dataset.id];
                if (targetNode) showInfoPanel(targetNode);
            });
        });
    }

    function hideInfoPanel() {
        infoPanel.classList.remove("visible");
    }

    // Handle resize
    window.addEventListener("resize", () => {
        const w = container.clientWidth;
        const h = container.clientHeight;
        svg.attr("width", w).attr("height", h);
        simulation.force("center", d3.forceCenter(w / 2, h / 2));
        simulation.alpha(0.3).restart();
    });

})();
</script>
</body>
</html>'''
