"""Terminal graph visualizer using rich.

Renders a visual representation of the skills graph directly in the terminal,
including a category tree view and a connections graph view.
"""

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.text import Text
from rich import box


def render_tree(skills: list[dict], graph_data: dict) -> None:
    """Render a category-grouped tree of skills with connections in the terminal.

    Args:
        skills: List of skill metadata dicts.
        graph_data: Graph dict with 'nodes', 'edges', and 'metadata' keys.
    """
    console = Console()
    edges = graph_data.get("edges", [])
    metadata = graph_data.get("metadata", {})

    n_skills = len(skills)
    n_edges = len(edges)
    n_categories = len(metadata.get("categories", []))

    # Header
    console.print()
    console.print(
        f"[bold #00e5b4]✦ Skillify[/] — "
        f"[dim]{n_skills} skills · {n_edges} connections · {n_categories} categories[/]"
    )
    console.print()

    # Group skills by category
    by_category: dict[str, list[dict]] = {}
    for skill in skills:
        cat = skill.get("category", "uncategorized")
        by_category.setdefault(cat, []).append(skill)

    # Build adjacency for showing connections inline
    node_map = {n["id"]: n for n in graph_data.get("nodes", [])}
    adjacency: dict[str, list[dict]] = {}
    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        adjacency.setdefault(src, []).append({"target": tgt, "type": edge["type"], "shared": edge.get("shared", [])})
        adjacency.setdefault(tgt, []).append({"target": src, "type": edge["type"], "shared": edge.get("shared", [])})

    # Render tree
    root = Tree("[bold #00e5b4]Skills[/]", guide_style="dim #14b8a6")

    for category in sorted(by_category.keys()):
        cat_skills = by_category[category]
        branch = root.add(f"[bold #2dd4bf]{category}[/] [dim]({len(cat_skills)})[/]")

        for skill in cat_skills:
            skill_id = skill.get("id", "")
            name = skill.get("name", "")
            keywords = skill.get("keywords", [])
            kw_str = ", ".join(keywords[:4])

            # Check connections
            connections = adjacency.get(skill_id, [])
            conn_count = len(connections)

            if conn_count > 0:
                label = f"[white]{name}[/] [dim]── {kw_str}[/] [#14b8a6]({conn_count} links)[/]"
            else:
                label = f"[white]{name}[/] [dim]── {kw_str}[/] [yellow](isolated)[/]"

            skill_branch = branch.add(label)

            # Show connections as sub-items
            for conn in connections[:3]:  # Limit to 3 shown
                target_node = node_map.get(conn["target"], {})
                target_name = target_node.get("label", conn["target"])
                shared = conn.get("shared", [])
                edge_type = conn["type"]

                if edge_type == "keyword":
                    shared_str = ", ".join(shared[:3])
                    skill_branch.add(f"[dim]──[#00e5b4]⟶[/] {target_name} [dim](shared: {shared_str})[/]")
                else:
                    skill_branch.add(f"[dim]──[#2dd4bf]⟶[/] {target_name} [dim](same category)[/]")

            if conn_count > 3:
                skill_branch.add(f"[dim]… and {conn_count - 3} more[/]")

    console.print(root)
    console.print()


def render_graph(skills: list[dict], graph_data: dict) -> None:
    """Render a connections-focused view of the graph in the terminal.

    Shows edges as a table with source → target and relationship info.

    Args:
        skills: List of skill metadata dicts.
        graph_data: Graph dict with 'nodes', 'edges', and 'metadata' keys.
    """
    console = Console()
    edges = graph_data.get("edges", [])
    nodes = graph_data.get("nodes", [])
    metadata = graph_data.get("metadata", {})

    node_map = {n["id"]: n for n in nodes}

    n_skills = len(skills)
    n_edges = len(edges)
    n_categories = len(metadata.get("categories", []))

    # Header
    console.print()
    console.print(
        f"[bold #00e5b4]✦ Skillify[/] — "
        f"[dim]{n_skills} skills · {n_edges} connections · {n_categories} categories[/]"
    )
    console.print()

    if not edges:
        console.print("[yellow]No connections found between skills.[/]")
        console.print()
        return

    # Connections table
    table = Table(
        title="[bold]Skill Connections[/]",
        box=box.ROUNDED,
        border_style="dim #14b8a6",
        header_style="bold #00e5b4",
        show_lines=False,
    )
    table.add_column("From", style="white", no_wrap=True)
    table.add_column("", style="#00e5b4", width=3, justify="center")
    table.add_column("To", style="white", no_wrap=True)
    table.add_column("Type", style="#2dd4bf", no_wrap=True)
    table.add_column("Shared", style="dim")

    # Sort edges: keyword edges first (more interesting), then by weight
    sorted_edges = sorted(edges, key=lambda e: (-1 if e["type"] == "keyword" else 0, -e.get("weight", 0)))

    for edge in sorted_edges:
        src = node_map.get(edge["source"], {}).get("label", edge["source"])
        tgt = node_map.get(edge["target"], {}).get("label", edge["target"])
        edge_type = edge["type"]
        shared = ", ".join(edge.get("shared", [])[:4])

        arrow = "⟶"
        table.add_row(src, arrow, tgt, edge_type, shared)

    console.print(table)
    console.print()

    # Isolated nodes
    connected_ids = set()
    for edge in edges:
        connected_ids.add(edge["source"])
        connected_ids.add(edge["target"])

    isolated = [n for n in nodes if n["id"] not in connected_ids]
    if isolated:
        console.print("[yellow]Isolated skills (no connections):[/]")
        for node in isolated:
            console.print(f"  [dim]○[/] {node['label']} [dim]— {node.get('description', '')[:50]}[/]")
        console.print()
