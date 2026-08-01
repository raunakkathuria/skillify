"""Scanner module for recursively scanning directories for skill files and extracting metadata."""

import fnmatch
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml


# Common English stopwords for keyword extraction
STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "must",
    "it", "its", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "what", "which", "who", "whom", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "not", "only", "same", "so", "than", "too",
    "very", "just", "because", "if", "then", "else", "about", "up", "out",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "again", "further", "once", "here", "there",
    "also", "over", "new", "old", "well", "way", "use", "used", "using",
    "one", "two", "first", "also", "make", "like", "get", "many", "any",
    "still", "however", "much", "since", "back", "even", "see", "come",
    "take", "know", "think", "say", "help", "tell", "give", "find",
}


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug.

    Normalizes unicode, lowercases, replaces non-alphanumeric characters with hyphens,
    and strips leading/trailing hyphens.

    Args:
        text: The text to slugify.

    Returns:
        A URL-safe slug string.
    """
    # Normalize unicode characters to ASCII equivalents
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # Lowercase
    text = text.lower()
    # Replace any non-alphanumeric character with a hyphen
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def extract_keywords_from_content(content: str, max_keywords: int = 10) -> list[str]:
    """Extract keywords from text content using simple term frequency.

    Splits content into words, removes stopwords and short tokens,
    counts frequency, and returns the top N most frequent terms.

    Args:
        content: The text content to extract keywords from.
        max_keywords: Maximum number of keywords to return.

    Returns:
        A list of keyword strings, ordered by frequency (most frequent first).
    """
    # Remove markdown formatting characters
    text = re.sub(r"[#*`\[\](){}|>~_=+]", " ", content)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Split into words, lowercase, keep only alphabetic tokens
    words = re.findall(r"[a-zA-Z]+", text.lower())
    # Filter stopwords and short words (less than 3 chars)
    filtered = [w for w in words if w not in STOPWORDS and len(w) >= 3]
    # Count frequency
    counter = Counter(filtered)
    # Return top N keywords
    return [word for word, _ in counter.most_common(max_keywords)]


def extract_skill_metadata(filepath: str) -> dict:
    """Extract skill metadata from a markdown file.

    Parses YAML frontmatter if present (between --- delimiters).
    Falls back to extracting name from the first H1 heading or filename,
    description from the first paragraph, and keywords via term frequency.

    Always includes: id, path, file_size, last_modified.

    Args:
        filepath: Path to the markdown file.

    Returns:
        A dictionary containing the extracted metadata.
    """
    filepath = os.path.abspath(filepath)
    stat = os.stat(filepath)
    file_size = stat.st_size
    last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    metadata: dict = {}
    body = content

    # Try to parse YAML frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if frontmatter_match:
        frontmatter_text = frontmatter_match.group(1)
        body = frontmatter_match.group(2)
        try:
            fm_data = yaml.safe_load(frontmatter_text)
            if isinstance(fm_data, dict):
                metadata["name"] = fm_data.get("name") or fm_data.get("title", "")
                metadata["description"] = fm_data.get("description", "")
                # Support both 'tags' and 'keywords'
                tags = fm_data.get("tags") or fm_data.get("keywords") or []
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")]
                metadata["keywords"] = tags
                metadata["category"] = fm_data.get("category", "")
                metadata["version"] = fm_data.get("version", "")
                metadata["author"] = fm_data.get("author", "")
        except yaml.YAMLError:
            # If YAML parsing fails, treat as no frontmatter
            body = content

    # Fallback extraction if no frontmatter or missing fields
    if not metadata.get("name"):
        # Try first H1 heading
        h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1_match:
            metadata["name"] = h1_match.group(1).strip()
        else:
            # Use filename without extension
            metadata["name"] = Path(filepath).stem

    if not metadata.get("description"):
        # Extract first paragraph after heading (or first paragraph of body)
        # Skip headings and blank lines, get first non-empty paragraph
        lines = body.split("\n")
        paragraph_lines: list[str] = []
        found_content = False
        for line in lines:
            stripped = line.strip()
            # Skip headings and empty lines before content
            if not found_content:
                if stripped and not stripped.startswith("#"):
                    found_content = True
                    paragraph_lines.append(stripped)
            else:
                if stripped:
                    paragraph_lines.append(stripped)
                else:
                    break  # End of paragraph
        metadata["description"] = " ".join(paragraph_lines)

    if not metadata.get("keywords"):
        metadata["keywords"] = extract_keywords_from_content(body)

    # Ensure all fields exist
    metadata.setdefault("category", "")
    metadata.setdefault("version", "")
    metadata.setdefault("author", "")

    # Always-present fields
    metadata["id"] = slugify(metadata["name"])
    metadata["path"] = filepath
    metadata["file_size"] = file_size
    metadata["last_modified"] = last_modified

    return metadata


def scan_directory(path: str, patterns: list[str] | None = None) -> list[dict]:
    """Recursively scan a directory for skill files and extract metadata.

    Walks the directory tree, matching files against the provided patterns.
    SKILL.md files take priority — if a directory contains SKILL.md, other
    markdown files in that same directory are skipped.

    Args:
        path: Root directory path to scan.
        patterns: List of filename patterns to match (supports glob wildcards).
                  Defaults to ['SKILL.md', '*.md'].

    Returns:
        A list of metadata dictionaries, one per matched skill file.
    """
    if patterns is None:
        patterns = ["SKILL.md", "*.md"]

    root_path = os.path.abspath(path)
    results: list[dict] = []
    seen_paths: set[str] = set()

    # Priority logic only applies when SKILL.md is explicitly listed as a pattern
    skill_md_priority = "SKILL.md" in patterns

    for dirpath, _dirnames, filenames in os.walk(root_path):
        # Check if SKILL.md exists in this directory (priority pattern)
        has_skill_md = skill_md_priority and "SKILL.md" in filenames

        for pattern in patterns:
            matching_files = fnmatch.filter(filenames, pattern)
            for filename in matching_files:
                # If we have SKILL.md and current pattern is a wildcard,
                # skip non-SKILL.md files in this directory
                if has_skill_md and pattern != "SKILL.md" and filename != "SKILL.md":
                    continue

                filepath = os.path.join(dirpath, filename)
                abs_filepath = os.path.abspath(filepath)

                # Avoid duplicates (a file may match multiple patterns)
                if abs_filepath in seen_paths:
                    continue
                seen_paths.add(abs_filepath)

                metadata = extract_skill_metadata(abs_filepath)
                # Store path as relative to scan root
                metadata["path"] = os.path.relpath(abs_filepath, root_path)
                results.append(metadata)

    return results
