"""SVG visualizer for the skills knowledge graph.

Generates a static/animated SVG that visualizes the index-to-skill lookup concept,
like a book's table of contents pointing to chapters. Also generates a graph SVG
showing skill relationships.
"""

import json
import math
import os
import random
from typing import Any


def generate_svg(graph_data: dict, output_dir: str, title: str = "skillify") -> None:
    """Generate an animated SVG visualization showing the index→skill concept.

    Creates a self-contained SVG with:
    - Terminal-style chrome (dark background, traffic light dots)
    - Left side: keyword index entries
    - Right side: skill names (the "chapters")
    - Animated lines connecting keywords to their matching skills

    Args:
        graph_data: Graph dict with 'nodes', 'edges', and 'metadata' keys.
        output_dir: Directory where graph.svg will be written.
        title: Title shown in the terminal header.
    """
    os.makedirs(output_dir, exist_ok=True)

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    metadata = graph_data.get("metadata", {})
    categories = metadata.get("categories", [])

    # Layout
    width = 900
    height = 420
    anim_duration = 10.0

    svg_parts: list[str] = []

    # SVG header
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        f'role="img" aria-label="skillify — index pointing to skills like a book table of contents">'
    )

    # Defs
    svg_parts.append('''<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#0a0c0f"/>
<stop offset="1" stop-color="#111417"/>
</linearGradient>
<linearGradient id="line-glow" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="#00e5b4"/>
<stop offset="1" stop-color="#14b8a6"/>
</linearGradient>
</defs>''')

    # Background
    svg_parts.append(
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="14" '
        f'fill="url(#bg)" stroke="#1e2329" stroke-width="1.5"/>'
    )

    # Traffic light dots
    svg_parts.append('<circle cx="28" cy="26" r="4.5" fill="#ff5f56"/>')
    svg_parts.append('<circle cx="46" cy="26" r="4.5" fill="#ffbd2e"/>')
    svg_parts.append('<circle cx="64" cy="26" r="4.5" fill="#27c93f"/>')

    # Title
    svg_parts.append(
        f'<text x="{width - 20}" y="30" text-anchor="end" font-size="10" '
        f'fill="#606876">{title}</text>'
    )

    # Divider line (subtle)
    mid_x = width // 2
    svg_parts.append(
        f'<line x1="{mid_x}" y1="50" x2="{mid_x}" y2="{height - 20}" '
        f'stroke="#1e2329" stroke-width="1" stroke-dasharray="4,4"/>'
    )

    # Left side header: "Index"
    svg_parts.append(
        '<text x="80" y="72" font-size="12" fill="#00e5b4" font-weight="600">'
        '📖  Index (keywords)</text>'
    )

    # Right side header: "Skills"
    svg_parts.append(
        f'<text x="{mid_x + 40}" y="72" font-size="12" fill="#00e5b4" font-weight="600">'
        '📄  Skills (loaded on demand)</text>'
    )

    # Build index entries from skills
    # Pick top keywords and map them to skills
    keyword_to_skills: dict[str, list[dict]] = {}
    for node in nodes:
        for kw in node.get("keywords", [])[:3]:
            keyword_to_skills.setdefault(kw, []).append(node)

    # Select the most interesting keywords (those that map to skills)
    # Pick up to 8 keywords, preferring ones that connect to different skills
    seen_skills: set[str] = set()
    index_entries: list[tuple[str, dict]] = []

    for kw in sorted(keyword_to_skills.keys(), key=lambda k: -len(keyword_to_skills[k])):
        for skill in keyword_to_skills[kw]:
            if skill["id"] not in seen_skills and len(index_entries) < 8:
                index_entries.append((kw, skill))
                seen_skills.add(skill["id"])
                break
        if len(index_entries) >= 8:
            break

    # If we have fewer than the total nodes, add remaining skills with their first keyword
    for node in nodes:
        if node["id"] not in seen_skills and len(index_entries) < 8:
            kw = node.get("keywords", ["skill"])[0] if node.get("keywords") else node["id"]
            index_entries.append((kw, node))
            seen_skills.add(node["id"])

    # Draw entries
    start_y = 100
    row_height = 38
    left_x = 80
    right_x = mid_x + 40

    for i, (keyword, skill) in enumerate(index_entries):
        y = start_y + i * row_height
        skill_name = skill.get("label", skill.get("name", skill["id"]))
        category = skill.get("category", "")

        # Animation timing: stagger each entry
        appear_time = 0.1 + i * 0.08
        line_start = appear_time + 0.02
        line_end = line_start + 0.04

        # Left: keyword
        svg_parts.append(
            f'<text x="{left_x}" y="{y}" font-size="11" fill="#a7aebd" opacity="0">'
            f'"{_escape_xml(keyword)}"'
            f'<animate attributeName="opacity" values="0;0;1;1" '
            f'keyTimes="0;{appear_time:.3f};{appear_time+0.02:.3f};1" '
            f'dur="{anim_duration}s" repeatCount="indefinite"/>'
            f'</text>'
        )

        # Connecting line (animated dash)
        line_y = y - 4
        line_x1 = left_x + len(keyword) * 7 + 30
        line_x2 = right_x - 10
        line_length = line_x2 - line_x1

        svg_parts.append(
            f'<line x1="{line_x1}" y1="{line_y}" x2="{line_x2}" y2="{line_y}" '
            f'stroke="#14b8a6" stroke-width="1" stroke-dasharray="4,3" '
            f'stroke-dashoffset="{line_length}" opacity="0.7">'
            f'<animate attributeName="stroke-dashoffset" '
            f'values="{line_length};{line_length};0;0" '
            f'keyTimes="0;{line_start:.3f};{line_end:.3f};1" '
            f'dur="{anim_duration}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0;0.7;0.7" '
            f'keyTimes="0;{line_start:.3f};{line_end:.3f};1" '
            f'dur="{anim_duration}s" repeatCount="indefinite"/>'
            f'</line>'
        )

        # Arrow head
        svg_parts.append(
            f'<text x="{line_x2 + 2}" y="{line_y + 4}" font-size="10" fill="#14b8a6" opacity="0">'
            f'→'
            f'<animate attributeName="opacity" values="0;0;1;1" '
            f'keyTimes="0;{line_end:.3f};{line_end+0.01:.3f};1" '
            f'dur="{anim_duration}s" repeatCount="indefinite"/>'
            f'</text>'
        )

        # Right: skill name + category badge
        skill_appear = line_end + 0.01
        svg_parts.append(
            f'<text x="{right_x + 10}" y="{y}" font-size="11" fill="#e8eaf0" '
            f'font-weight="600" opacity="0">'
            f'{_escape_xml(skill_name)}'
            f'<animate attributeName="opacity" values="0;0;1;1" '
            f'keyTimes="0;{skill_appear:.3f};{skill_appear+0.02:.3f};1" '
            f'dur="{anim_duration}s" repeatCount="indefinite"/>'
            f'</text>'
        )

        # Category tag (small, muted)
        if category:
            svg_parts.append(
                f'<text x="{right_x + 10}" y="{y + 14}" font-size="8" fill="#606876" opacity="0">'
                f'{_escape_xml(category)}'
                f'<animate attributeName="opacity" values="0;0;0.8;0.8" '
                f'keyTimes="0;{skill_appear:.3f};{skill_appear+0.02:.3f};1" '
                f'dur="{anim_duration}s" repeatCount="indefinite"/>'
                f'</text>'
            )

    # Bottom: command line demo
    cmd_y = height - 40
    cmd_appear = 0.1 + len(index_entries) * 0.08 + 0.1
    svg_parts.append(
        f'<text x="28" y="{cmd_y}" font-size="10" fill="#00e5b4" opacity="0">'
        f'$ skillify search "deployment"  →  CI/CD Deployment (deployment/SKILL.md)'
        f'<animate attributeName="opacity" values="0;0;1;1" '
        f'keyTimes="0;{cmd_appear:.3f};{cmd_appear+0.03:.3f};1" '
        f'dur="{anim_duration}s" repeatCount="indefinite"/>'
        f'</text>'
    )

    # Close SVG
    svg_parts.append('</svg>')

    # Write file
    svg_content = "\n".join(svg_parts)
    output_path = os.path.join(output_dir, "graph.svg")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)


def _escape_xml(text: str) -> str:
    """Escape special XML characters in text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
