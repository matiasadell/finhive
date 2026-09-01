from __future__ import annotations

from portfolio_intel.data.schema import (
    DETAIL_JOIN_COLUMN,
    RUAI_JOIN_COLUMN,
    RUAI_USE_CASE_COLUMNS,
    USE_CASE_DETAIL_COLUMNS,
)
from portfolio_intel.data.store import LocalCSVStore, load_portfolio_data
from portfolio_intel.data.synthetic import generate_use_cases


def test_generator_is_deterministic():
    first = generate_use_cases()
    second = generate_use_cases()
    assert first == second


def test_ruai_csv_matches_schema():
    df = LocalCSVStore().get_ruai_inventory()
    assert list(df.columns) == RUAI_USE_CASE_COLUMNS


def test_detail_csv_matches_schema():
    df = LocalCSVStore().get_use_case_detail()
    assert list(df.columns) == USE_CASE_DETAIL_COLUMNS


def test_join_has_no_orphans():
    ruai = LocalCSVStore().get_ruai_inventory()
    detail = LocalCSVStore().get_use_case_detail()
    assert set(ruai[RUAI_JOIN_COLUMN]) == set(detail[DETAIL_JOIN_COLUMN])


def test_load_portfolio_data_defaults_to_local(monkeypatch):
    monkeypatch.delenv("PORTFOLIO_INTEL_DATA_BACKEND", raising=False)
    store = load_portfolio_data()
    assert isinstance(store, LocalCSVStore)


def test_get_use_cases_row_count(use_cases_df):
    assert len(use_cases_df) == 30
    assert use_cases_df["use case id"].nunique() == 30
