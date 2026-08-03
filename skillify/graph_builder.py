"""Graph builder that constructs skill relationship graphs.

This module builds a graph data structure from skill metadata, identifying
relationships between skills based on shared categories and keywords.
The resulting graph can be used for visualization and navigation.
"""

import json
import os
from datetime import datetime, timezone
from itertools import combinations
from typing import Any


def build_graph(skills: list[dict]) -> dict:
    """Build a relationship graph from skill metadata.

    Creates a graph where:
    - Nodes represent individual skills
    - Edges connect skills that share the same category or 2+ keywords

    Edge types:
    - 'category': Skills in the same category (weight: 1)
    - 'keyword': Skills sharing 2+ keywords (weight: number of shared keywords)

    Pure — call `write_graph` to persist the result. Tiering needs the graph
    without the side effect.

    Args:
        skills: List of skill metadata dicts. Each should contain at minimum:
            id, name, description, keywords, category, path.

    Returns:
        The complete graph dict with nodes, edges, and metadata.
    """
    nodes = _build_nodes(skills)
    edges = _build_edges(skills)

    categories = sorted(set(skill.get("category", "uncategorized") for skill in skills))

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "categories": categories,
            "generated": datetime.now(timezone.utc).isoformat(),
        },
    }


def write_graph(graph: dict, output_dir: str) -> str:
    """Write a graph dict to graph.json.

    Args:
        graph: Graph dict from `build_graph`.
        output_dir: Directory to write into. Created if missing.

    Returns:
        The path written.
    """
    os.makedirs(output_dir, exist_ok=True)
    graph_path = os.path.join(output_dir, "graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    return graph_path


def _build_nodes(skills: list[dict]) -> list[dict]:
    """Build graph nodes from skill metadata.

    Each skill becomes a node with its core attributes.

    Args:
        skills: List of skill metadata dicts.

    Returns:
        List of node dicts with id, label, category, keywords, description, path.
    """
    nodes = []
    for skill in skills:
        node = {
            "id": skill.get("id", ""),
            "label": skill.get("name", ""),
            "category": skill.get("category", "uncategorized"),
            "keywords": skill.get("keywords", []),
            "description": skill.get("description", ""),
            "path": skill.get("path", ""),
        }
        nodes.append(node)
    return nodes


def _build_edges(skills: list[dict]) -> list[dict]:
    """Build graph edges based on shared categories and keywords.

    Connects skills that:
    - Share the same category (edge type: 'category', weight: 1)
    - Share 2 or more keywords (edge type: 'keyword', weight: count of shared keywords)

    A pair of skills can have multiple edges (one category edge and one keyword edge).

    Args:
        skills: List of skill metadata dicts.

    Returns:
        List of edge dicts with source, target, type, weight, and shared fields.
    """
    edges: list[dict] = []

    # Index skills by their position for pairwise comparison
    skill_pairs = list(combinations(range(len(skills)), 2))

    for i, j in skill_pairs:
        skill_a = skills[i]
        skill_b = skills[j]

        id_a = skill_a.get("id", "")
        id_b = skill_b.get("id", "")

        # Category edge
        cat_a = skill_a.get("category", "uncategorized")
        cat_b = skill_b.get("category", "uncategorized")
        if cat_a == cat_b and cat_a:
            edges.append({
                "source": id_a,
                "target": id_b,
                "type": "category",
                "weight": 1,
                "shared": [cat_a],
            })

        # Keyword edge (2+ shared keywords required)
        keywords_a = set(kw.lower() for kw in skill_a.get("keywords", []))
        keywords_b = set(kw.lower() for kw in skill_b.get("keywords", []))
        shared_keywords = sorted(keywords_a & keywords_b)

        if len(shared_keywords) >= 2:
            edges.append({
                "source": id_a,
                "target": id_b,
                "type": "keyword",
                "weight": len(shared_keywords),
                "shared": shared_keywords,
            })

    return edges
