"""Shared fixtures for skillify tests."""

import textwrap

import pytest


def write_skill(directory, name, description, keywords=(), category=""):
    """Write a SKILL.md with frontmatter into `directory`.

    Args:
        directory: pathlib.Path to write into. Created if missing.
        name: Skill name for the frontmatter.
        description: Skill description.
        keywords: Iterable of keyword strings.
        category: Category string.

    Returns:
        The path written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    front = [f"name: {name}", f"description: {description}"]
    if keywords:
        front.append("keywords: [" + ", ".join(keywords) + "]")
    if category:
        front.append(f"category: {category}")

    path.write_text(
        "---\n" + "\n".join(front) + "\n---\n\n"
        + textwrap.dedent(f"""\
            # {name}

            {description}
            """)
    )
    return path


@pytest.fixture
def library(tmp_path):
    """A small skills library with a known shape."""
    write_skill(
        tmp_path / "db-migration",
        "Database Migration",
        "Safe database schema migration process with rollback support",
        keywords=["database", "migration", "schema", "sql", "rollback"],
        category="infrastructure",
    )
    write_skill(
        tmp_path / "code-review",
        "Code Review",
        "Review pull requests for correctness and security issues",
        keywords=["review", "pullrequest", "quality", "security"],
        category="quality",
    )
    write_skill(
        tmp_path / "deployment",
        "CI/CD Deployment",
        "Ship a release through the deployment pipeline",
        keywords=["deployment", "release", "pipeline"],
        category="infrastructure",
    )
    return tmp_path
