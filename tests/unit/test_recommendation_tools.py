from __future__ import annotations

from portfolio_intel.tools.recommendation_tools import generate_portfolio_recommendations


def test_every_use_case_gets_exactly_one_recommendation(use_cases_df):
    recs = generate_portfolio_recommendations(use_cases_df)
    ids = [r["use_case_id"] for r in recs]
    assert len(ids) == len(use_cases_df)
    assert len(set(ids)) == len(ids)  # sin duplicados


def test_duplicate_precedence_over_low_priority(use_cases_df):
    recs = {r["use_case_id"]: r for r in generate_portfolio_recommendations(use_cases_df)}
    assert recs["UC-011"]["action"] == "Consolidate"
    assert "UC-012" in recs["UC-011"]["reason"]


def test_scale_tier_recommended_scale(use_cases_df):
    recs = {r["use_case_id"]: r for r in generate_portfolio_recommendations(use_cases_df)}
    for uid in ("UC-001", "UC-002", "UC-003", "UC-004", "UC-005", "UC-006"):
        assert recs[uid]["action"] == "Scale", f"{uid} debería ser Scale, fue {recs[uid]['action']}"


def test_stalled_low_priority_ideation_recommended_discontinue(use_cases_df):
    recs = {r["use_case_id"]: r for r in generate_portfolio_recommendations(use_cases_df)}
    assert recs["UC-021"]["action"] == "Discontinue"


def test_reason_cites_real_evidence(use_cases_df):
    recs = {r["use_case_id"]: r for r in generate_portfolio_recommendations(use_cases_df)}
    rec = recs["UC-001"]
    assert str(rec["evidence"]["priority_score"]) in rec["reason"]
