"""Tests for skill search ranking."""

import pytest

from skillify.indexer import search_skills
from skillify.scanner import scan_directory


@pytest.fixture
def skills(library):
    """Scanned skills from the shared library fixture."""
    return scan_directory(library)


def test_sentence_query_finds_the_right_skill(skills):
    """The regression that motivates tokenized scoring.

    Literal substring matching of the whole query returned nothing here, because
    the phrase appears verbatim in no field. An agent phrases queries this way.
    """
    results = search_skills(skills, "how do I safely change the database schema")

    assert results, "sentence-shaped query returned nothing"
    assert results[0]["id"] == "database-migration"


def test_single_word_query_still_works(skills):
    """Humans type single words at the CLI; that path must not regress."""
    results = search_skills(skills, "database")

    assert results[0]["id"] == "database-migration"


def test_name_match_outranks_description_match(skills):
    """A skill named for the query beats one that merely mentions it."""
    results = search_skills(skills, "deployment")

    assert results[0]["id"] == "ci-cd-deployment"


def test_unrelated_query_returns_nothing(skills):
    """Scoring must not match everything just because the query is long."""
    assert search_skills(skills, "knitting patterns for wool socks") == []


def test_empty_query_returns_nothing(skills):
    """An empty query is a caller mistake, not a request for the whole library."""
    assert search_skills(skills, "") == []
    assert search_skills(skills, "   ") == []


def test_limit_is_respected(skills):
    """The limit bounds what reaches the agent's context."""
    assert len(search_skills(skills, "deployment database review", limit=2)) == 2


def test_ranking_is_stable_for_equal_scores(skills):
    """Equal scores tie-break by name so output does not shuffle between runs."""
    first = [s["id"] for s in search_skills(skills, "infrastructure")]
    second = [s["id"] for s in search_skills(skills, "infrastructure")]

    assert first == second
