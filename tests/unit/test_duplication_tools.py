"""`tools/duplication_tools.py` -- ver los 4 clusters engineered en `data/sample_docs/README.md`."""

from __future__ import annotations

from portfolio_intel.tools.duplication_tools import (
    duplicated_use_case_ids,
    find_duplicate_use_cases,
    get_use_case_overlap_detail,
)

_EXPECTED_CLUSTERS = [
    {"UC-007", "UC-008"},
    {"UC-009", "UC-010"},
    {"UC-011", "UC-012"},
    {"UC-013", "UC-014"},
]


def test_finds_exactly_the_engineered_clusters(use_cases_df):
    pairs = find_duplicate_use_cases(use_cases_df)
    found_clusters = {frozenset({p["use_case_id_a"], p["use_case_id_b"]}) for p in pairs}
    assert found_clusters == set(map(frozenset, _EXPECTED_CLUSTERS))


def test_no_false_positives_across_unrelated_cases(use_cases_df):
    """Regresión del bug real encontrado con la plantilla de texto genérica
    (ver el commit de Tasks 5-8): casos sin relación real no deben matchear."""
    pairs = find_duplicate_use_cases(use_cases_df)
    all_ids_in_pairs = {p["use_case_id_a"] for p in pairs} | {p["use_case_id_b"] for p in pairs}
    expected_ids = {uid for cluster in _EXPECTED_CLUSTERS for uid in cluster}
    assert all_ids_in_pairs == expected_ids


def test_duplicated_use_case_ids_matches_pairs(use_cases_df):
    ids = duplicated_use_case_ids(use_cases_df)
    expected_ids = {uid for cluster in _EXPECTED_CLUSTERS for uid in cluster}
    assert ids == expected_ids


def test_overlap_detail_for_specific_case(use_cases_df):
    overlaps = get_use_case_overlap_detail(use_cases_df, "UC-007")
    assert len(overlaps) == 1
    assert {overlaps[0]["use_case_id_a"], overlaps[0]["use_case_id_b"]} == {"UC-007", "UC-008"}


def test_case_with_no_overlap_returns_empty(use_cases_df):
    assert get_use_case_overlap_detail(use_cases_df, "UC-001") == []
