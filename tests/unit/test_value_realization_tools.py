"""`tools/value_realization_tools.py` -- 3 señales, sin LLM."""

from __future__ import annotations

from datetime import date

from portfolio_intel.tools.value_realization_tools import (
    compute_value_realization_status,
    explain_value_status,
    get_at_risk_use_cases,
)

_ENGINEERED_AT_RISK_IDS = ["UC-011", "UC-015", "UC-016", "UC-017", "UC-018", "UC-019"]
_SCALE_TIER_IDS = ["UC-001", "UC-002", "UC-003", "UC-004", "UC-005", "UC-006"]


def test_engineered_at_risk_cases_flagged(use_cases_df):
    scored = compute_value_realization_status(use_cases_df, as_of=date(2026, 9, 1))
    statuses = scored.set_index("use case id").loc[_ENGINEERED_AT_RISK_IDS, "value_status"]
    assert (statuses != "on_track").all()


def test_scale_tier_is_on_track(use_cases_df):
    scored = compute_value_realization_status(use_cases_df, as_of=date(2026, 9, 1))
    statuses = scored.set_index("use case id").loc[_SCALE_TIER_IDS, "value_status"]
    assert (statuses == "on_track").all()


def test_missing_barrier_does_not_false_positive(use_cases_df):
    """Regresión del bug real de NaN: una celda vacía de `insight learned or
    barriers` no debe contar como señal de riesgo (ver commit de Tasks 5-8)."""
    scored = compute_value_realization_status(use_cases_df, as_of=date(2026, 9, 1))
    healthy = scored[scored["use case id"].isin(_SCALE_TIER_IDS)]
    assert not healthy["signal_documented_barrier"].any()


def test_get_at_risk_use_cases_subset(use_cases_df):
    at_risk = get_at_risk_use_cases(
        compute_value_realization_status(use_cases_df, as_of=date(2026, 9, 1))
    )
    assert set(_ENGINEERED_AT_RISK_IDS).issubset(set(at_risk["use case id"]))


def test_explain_value_status_renders_signals(use_cases_df):
    scored = compute_value_realization_status(use_cases_df, as_of=date(2026, 9, 1))
    explanation = explain_value_status(scored, "UC-015")
    assert "cost_overrun" in explanation
    assert "timeline_breach" in explanation
    assert "documented_barrier" in explanation
