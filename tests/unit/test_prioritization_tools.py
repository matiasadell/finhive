"""`tools/prioritization_tools.py` -- ver el docstring del módulo para los pesos."""

from __future__ import annotations

from portfolio_intel.tools.prioritization_tools import (
    compute_priority_scores,
    explain_priority_score,
    get_top_priorities,
)

_SCALE_TIER_IDS = ["UC-001", "UC-002", "UC-003", "UC-004", "UC-005", "UC-006"]
_DISCONTINUE_TIER_IDS = ["UC-020", "UC-021", "UC-022", "UC-023", "UC-024"]


def test_scale_tier_scores_above_discontinue_tier(use_cases_df):
    scored = compute_priority_scores(use_cases_df)
    by_id = scored.set_index("use case id")["priority_score"]
    assert by_id.loc[_SCALE_TIER_IDS].min() > by_id.loc[_DISCONTINUE_TIER_IDS].max()


def test_top_priorities_includes_scale_tier(use_cases_df):
    top = get_top_priorities(use_cases_df, n=6)
    assert set(top["use case id"]) == set(_SCALE_TIER_IDS)


def test_explain_priority_score_cites_real_values(use_cases_df):
    scored = compute_priority_scores(use_cases_df)
    explanation = explain_priority_score(scored, "UC-001")
    assert "UC-001" in explanation
    assert "priority_score" in explanation
    assert "peso" in explanation  # los pesos van citados, no solo el score final


def test_explain_priority_score_unknown_id(use_cases_df):
    scored = compute_priority_scores(use_cases_df)
    explanation = explain_priority_score(scored, "UC-999")
    assert "no se encontró" in explanation.lower()
