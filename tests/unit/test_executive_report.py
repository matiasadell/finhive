from __future__ import annotations

from portfolio_intel.reporting.executive_report import render_executive_report


def test_report_is_nonempty_markdown(use_cases_df):
    report = render_executive_report(use_cases_df)
    assert report.startswith("# Portfolio Intel")
    assert "## Resumen ejecutivo" in report
    assert "## Top prioridades" in report
    assert "## Reuso y duplicación" in report
    assert "## Riesgos de value realization" in report
    assert "## Recomendaciones por caso de uso" in report


def test_report_cites_known_use_case_ids(use_cases_df):
    report = render_executive_report(use_cases_df)
    # UC-006: top prioridad. UC-007/UC-008: cluster de duplicados.
    assert "UC-006" in report
    assert "UC-007" in report
    assert "UC-008" in report


def test_report_is_reproducible(use_cases_df):
    assert render_executive_report(use_cases_df) == render_executive_report(use_cases_df)
