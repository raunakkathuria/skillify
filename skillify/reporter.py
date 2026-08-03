"""Report generator that produces a comprehensive Skillify report.

This module analyzes skill metadata and graph data to generate a markdown
report covering categories, clusters, hubs, keyword frequencies, suggested
groupings, and isolated skills.
"""

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def generate_report(skills: list[dict], graph_data: dict, output_dir: str) -> None:
    """Generate SKILLIFY_REPORT.md from skill metadata and graph data.

    Produces a comprehensive markdown report that includes:
    - Overview statistics
    - Category breakdown table
    - Key clusters (highly interconnected skill groups)
    - Most connected skills (hub nodes)
    - Keyword frequency analysis
    - Suggested groupings based on keyword overlap
    - Isolated skills with no connections

    Args:
        skills: List of skill metadata dicts containing id, name, description,
            keywords, category, and path fields.
        graph_data: Graph dict with 'nodes', 'edges', and 'metadata' keys,
            as produced by graph_builder.build_graph().
        output_dir: Directory path where SKILLIFY_REPORT.md will be written.
    """
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    edges = graph_data.get("edges", [])
    nodes = graph_data.get("nodes", [])

    # Compute all analytics
    categories = _count_categories(skills)
    total_skills = len(skills)
    total_edges = len(edges)
    most_connected = _most_connected_skill(graph_data)
    largest_cat = _largest_category(categories)
    clusters = find_clusters(graph_data)
    hubs = find_hubs(graph_data)
    kw_freq = keyword_frequency(skills)
    isolated = find_isolated(graph_data)
    groupings = _suggest_groupings(graph_data, skills)

    # Build markdown
    lines: list[str] = []

    # Header
    lines.append("# Skillify Report")
    lines.append("")
    lines.append(f"> Generated on {now}")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append(f"- **Total Skills:** {total_skills}")
    lines.append(f"- **Categories:** {len(categories)}")
    lines.append(f"- **Connections:** {total_edges} edges in the knowledge graph")
    if most_connected:
        lines.append(
            f"- **Most Connected Skill:** {most_connected['name']} "
            f"({most_connected['connections']} connections)"
        )
    else:
        lines.append("- **Most Connected Skill:** N/A (no connections)")
    if largest_cat:
        lines.append(
            f"- **Largest Category:** {largest_cat['name']} "
            f"({largest_cat['count']} skills)"
        )
    else:
        lines.append("- **Largest Category:** N/A")
    lines.append("")

    # Category Breakdown
    lines.append("## Category Breakdown")
    lines.append("")
    lines.append("| Category | Skills | % of Total |")
    lines.append("|----------|--------|------------|")
    for cat_name, count in sorted(categories.items(), key=lambda x: -x[1]):
        pct = round(count / total_skills * 100) if total_skills > 0 else 0
        lines.append(f"| {cat_name} | {count} | {pct}% |")
    lines.append("")

    # Key Clusters
    lines.append("## Key Clusters")
    lines.append("")
    lines.append("Skills that are highly interconnected (share many keywords):")
    lines.append("")
    if clusters:
        for cluster in clusters:
            lines.append(f"### Cluster: \"{cluster['theme']}\"")
            lines.append(f"- {', '.join(cluster['skills'])}")
            lines.append(f"- Shared keywords: {', '.join(cluster['shared_keywords'])}")
            lines.append("")
    else:
        lines.append("*No significant clusters found.*")
        lines.append("")

    # Most Connected Skills (Hubs)
    lines.append("## Most Connected Skills (Hubs)")
    lines.append("")
    lines.append("| Skill | Connections | Categories it bridges |")
    lines.append("|-------|-------------|----------------------|")
    if hubs:
        for hub in hubs:
            bridged = ", ".join(hub["categories"])
            lines.append(f"| {hub['name']} | {hub['connections']} | {bridged} |")
    else:
        lines.append("| *None* | 0 | — |")
    lines.append("")

    # Keyword Frequency
    lines.append("## Keyword Frequency")
    lines.append("")
    lines.append("| Keyword | Appears in N skills |")
    lines.append("|---------|--------------------|")
    for kw, count in kw_freq[:20]:  # Top 20
        lines.append(f"| {kw} | {count} |")
    lines.append("")

    # Suggested Groupings
    lines.append("## Suggested Groupings")
    lines.append("")
    lines.append(
        "Based on keyword overlap, these skills might benefit from being grouped:"
    )
    if groupings:
        for group in groupings:
            skill_names = " + ".join(group["skills"])
            shared = ", ".join(group["shared_keywords"])
            lines.append(
                f"- Group: \"{group['name']}\" → {skill_names} (share: {shared})"
            )
    else:
        lines.append("- *No suggested groupings found.*")
    lines.append("")

    # Isolated Skills
    lines.append("## Isolated Skills")
    lines.append("")
    lines.append(
        "Skills with no connections to others (potential gaps or unique specializations):"
    )
    if isolated:
        for node in isolated:
            desc = node.get("description", "No description")
            lines.append(f"- {node['label']} — {desc}")
    else:
        lines.append("- *All skills have at least one connection.*")
    lines.append("")

    # Write report
    report_path = os.path.join(output_dir, "SKILLIFY_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def find_clusters(graph_data: dict) -> list[dict]:
    """Find groups of highly connected nodes that form clusters.

    A cluster is a group of 3+ nodes that are all interconnected via keyword
    edges (indicating shared keywords). Uses a simple clique-detection approach
    on keyword edges.

    Args:
        graph_data: Graph dict with 'nodes' and 'edges' keys.

    Returns:
        List of cluster dicts, each containing:
        - theme: A representative label for the cluster
        - skills: List of skill names in the cluster
        - shared_keywords: Keywords shared across all cluster members
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    # Build adjacency for keyword edges only
    node_map: dict[str, dict] = {n["id"]: n for n in nodes}
    keyword_adj: dict[str, dict[str, list[str]]] = defaultdict(dict)

    for edge in edges:
        if edge.get("type") == "keyword":
            source = edge["source"]
            target = edge["target"]
            shared = edge.get("shared", [])
            keyword_adj[source][target] = shared
            keyword_adj[target][source] = shared

    # Find triangles (3-cliques) as basic clusters
    visited_clusters: set[tuple] = set()
    clusters: list[dict] = []

    for node_id in keyword_adj:
        neighbors = set(keyword_adj[node_id].keys())
        for neighbor in neighbors:
            # Find common neighbors to form triangles
            neighbor_neighbors = set(keyword_adj.get(neighbor, {}).keys())
            common = neighbors & neighbor_neighbors
            for third in common:
                cluster_key = tuple(sorted([node_id, neighbor, third]))
                if cluster_key in visited_clusters:
                    continue
                visited_clusters.add(cluster_key)

                # Compute shared keywords across all three pairs
                kw_ab = set(keyword_adj[node_id].get(neighbor, []))
                kw_ac = set(keyword_adj[node_id].get(third, []))
                kw_bc = set(keyword_adj[neighbor].get(third, []))
                # Keywords that appear in at least 2 of the 3 pairs
                all_kws = kw_ab | kw_ac | kw_bc
                common_kws = sorted(
                    kw for kw in all_kws
                    if sum([kw in kw_ab, kw in kw_ac, kw in kw_bc]) >= 2
                )

                if not common_kws:
                    continue

                skill_names = []
                for sid in cluster_key:
                    name = node_map.get(sid, {}).get("label", sid)
                    skill_names.append(name)

                theme = common_kws[0] if common_kws else "mixed"
                clusters.append({
                    "theme": theme,
                    "skills": skill_names,
                    "shared_keywords": common_kws,
                })

    # Sort clusters by number of shared keywords (most interconnected first)
    clusters.sort(key=lambda c: -len(c["shared_keywords"]))
    return clusters


def connection_counts(graph_data: dict) -> dict[str, int]:
    """Count how many edges touch each node.

    Args:
        graph_data: Graph dict with an 'edges' key.

    Returns:
        Mapping of node id to edge count. Nodes with no edges are absent.
    """
    counts: dict[str, int] = defaultdict(int)
    for edge in graph_data.get("edges", []):
        counts[edge["source"]] += 1
        counts[edge["target"]] += 1
    return counts


def find_hubs(graph_data: dict) -> list[dict]:
    """Find nodes with the most connections (hub nodes).

    A hub is a skill that connects to many other skills, potentially bridging
    multiple categories.

    Args:
        graph_data: Graph dict with 'nodes' and 'edges' keys.

    Returns:
        List of hub dicts sorted by connection count (descending), each containing:
        - name: Skill name
        - id: Skill id
        - connections: Total number of connections
        - categories: List of unique categories this skill bridges
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    node_map: dict[str, dict] = {n["id"]: n for n in nodes}
    connection_count = connection_counts(graph_data)
    connected_nodes: dict[str, set[str]] = defaultdict(set)

    for edge in edges:
        connected_nodes[edge["source"]].add(edge["target"])
        connected_nodes[edge["target"]].add(edge["source"])

    if not connection_count:
        return []

    hubs: list[dict] = []
    for node_id, count in sorted(connection_count.items(), key=lambda x: -x[1]):
        node = node_map.get(node_id, {})
        # Find categories bridged: own category + categories of connected nodes
        categories_bridged: set[str] = set()
        own_cat = node.get("category", "uncategorized")
        categories_bridged.add(own_cat)
        for connected_id in connected_nodes[node_id]:
            connected_node = node_map.get(connected_id, {})
            cat = connected_node.get("category", "uncategorized")
            categories_bridged.add(cat)

        hubs.append({
            "name": node.get("label", node_id),
            "id": node_id,
            "connections": count,
            "categories": sorted(categories_bridged),
        })

    # Return top 10 hubs
    return hubs[:10]


def keyword_frequency(skills: list[dict]) -> list[tuple[str, int]]:
    """Count keyword occurrences across all skills.

    Args:
        skills: List of skill metadata dicts containing 'keywords' lists.

    Returns:
        List of (keyword, count) tuples sorted by count descending.
    """
    freq: dict[str, int] = defaultdict(int)

    for skill in skills:
        keywords = skill.get("keywords", [])
        for kw in keywords:
            freq[kw.lower()] += 1

    return sorted(freq.items(), key=lambda x: (-x[1], x[0]))


def find_isolated(graph_data: dict) -> list[dict]:
    """Find nodes with no edges (isolated/disconnected skills).

    Args:
        graph_data: Graph dict with 'nodes' and 'edges' keys.

    Returns:
        List of node dicts for skills that have zero connections.
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    connected_ids: set[str] = set()
    for edge in edges:
        connected_ids.add(edge["source"])
        connected_ids.add(edge["target"])

    isolated: list[dict] = []
    for node in nodes:
        if node["id"] not in connected_ids:
            isolated.append(node)

    return isolated


def _count_categories(skills: list[dict]) -> dict[str, int]:
    """Count skills per category.

    Args:
        skills: List of skill metadata dicts.

    Returns:
        Dict mapping category name to skill count.
    """
    categories: dict[str, int] = defaultdict(int)
    for skill in skills:
        cat = skill.get("category", "uncategorized")
        categories[cat] += 1
    return dict(categories)


def _largest_category(categories: dict[str, int]) -> dict[str, Any] | None:
    """Find the category with the most skills.

    Args:
        categories: Dict mapping category name to skill count.

    Returns:
        Dict with 'name' and 'count' keys, or None if no categories.
    """
    if not categories:
        return None
    name = max(categories, key=categories.get)  # type: ignore[arg-type]
    return {"name": name, "count": categories[name]}


def _most_connected_skill(graph_data: dict) -> dict[str, Any] | None:
    """Find the skill with the most connections.

    Args:
        graph_data: Graph dict with 'nodes' and 'edges' keys.

    Returns:
        Dict with 'name' and 'connections' keys, or None if no edges.
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not edges:
        return None

    node_map: dict[str, dict] = {n["id"]: n for n in nodes}
    connection_count: dict[str, int] = defaultdict(int)

    for edge in edges:
        connection_count[edge["source"]] += 1
        connection_count[edge["target"]] += 1

    if not connection_count:
        return None

    top_id = max(connection_count, key=connection_count.get)  # type: ignore[arg-type]
    node = node_map.get(top_id, {})
    return {
        "name": node.get("label", top_id),
        "connections": connection_count[top_id],
    }


def _suggest_groupings(graph_data: dict, skills: list[dict]) -> list[dict]:
    """Suggest skill groupings based on keyword edge overlap.

    Identifies pairs of skills with strong keyword overlap that are in
    different categories, suggesting they could be grouped together.

    Args:
        graph_data: Graph dict with 'nodes' and 'edges' keys.
        skills: List of skill metadata dicts.

    Returns:
        List of grouping dicts, each containing:
        - name: A suggested group name derived from shared keywords
        - skills: List of skill names in the group
        - shared_keywords: Keywords shared between the skills
    """
    edges = graph_data.get("edges", [])
    nodes = graph_data.get("nodes", [])
    node_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # Find keyword edges with high weight (3+ shared keywords) or
    # cross-category keyword edges (2+ shared keywords)
    groupings: list[dict] = []
    seen_pairs: set[tuple] = set()

    for edge in edges:
        if edge.get("type") != "keyword":
            continue

        source = edge["source"]
        target = edge["target"]
        pair_key = tuple(sorted([source, target]))

        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        shared = edge.get("shared", [])
        source_node = node_map.get(source, {})
        target_node = node_map.get(target, {})

        source_cat = source_node.get("category", "uncategorized")
        target_cat = target_node.get("category", "uncategorized")

        # Suggest grouping if cross-category or high overlap
        if source_cat != target_cat or len(shared) >= 3:
            group_name = shared[0] if shared else "mixed"
            groupings.append({
                "name": group_name,
                "skills": [
                    source_node.get("label", source),
                    target_node.get("label", target),
                ],
                "shared_keywords": shared,
            })

    # Sort by number of shared keywords
    groupings.sort(key=lambda g: -len(g["shared_keywords"]))
    return groupings[:15]  # Limit to 15 suggestions
