"""Tests for scanning and unique id assignment."""

from skillify.differ import compute_diff
from skillify.scanner import scan_directory, tokenize

from conftest import write_skill


def test_colliding_names_get_distinct_ids(tmp_path):
    """Two skills with the same name must not share an id.

    `id` is the key `load_skill` resolves, so a collision would silently serve
    the wrong file.
    """
    write_skill(tmp_path / "alpha", "Testing", "Alpha flavour of testing")
    write_skill(tmp_path / "beta", "Testing", "Beta flavour of testing")

    skills = scan_directory(tmp_path)
    ids = [s["id"] for s in skills]

    assert len(skills) == 2
    assert len(set(ids)) == 2, f"ids collided: {ids}"
    assert "testing" in ids  # the first by path keeps the clean slug


def test_colliding_skills_both_appear_in_diff(tmp_path):
    """Colliding ids used to make one skill vanish from the diff entirely."""
    write_skill(tmp_path / "alpha", "Testing", "Alpha flavour")
    write_skill(tmp_path / "beta", "Testing", "Beta flavour")

    diff = compute_diff(scan_directory(tmp_path), str(tmp_path / "missing.json"))

    assert len(diff["added"]) == 2


def test_ids_are_deterministic(tmp_path):
    """Repeat scans must produce identical ids, or --check reports false staleness."""
    write_skill(tmp_path / "alpha", "Testing", "Alpha flavour")
    write_skill(tmp_path / "beta", "Testing", "Beta flavour")
    write_skill(tmp_path / "gamma", "Testing", "Gamma flavour")

    first = {s["path"]: s["id"] for s in scan_directory(tmp_path)}
    second = {s["path"]: s["id"] for s in scan_directory(tmp_path)}

    assert first == second
    assert len(set(first.values())) == 3


def test_scan_paths_are_relative_to_root(library):
    """Paths are relative, which is why load_skill needs the root to resolve them."""
    for skill in scan_directory(library):
        assert not skill["path"].startswith("/")


def test_tokenize_drops_stopwords_and_short_tokens():
    """Tokenization is shared by keyword extraction and search scoring."""
    assert tokenize("How do I review the Database schema") == ["review", "database", "schema"]


def test_tokenize_keeps_digits():
    """Names like 'S3' or 'OAuth2' must survive tokenization."""
    assert "oauth2" in tokenize("OAuth2 flows")
