"""El golden set completo (`data/eval/golden_set.json`) tiene que pasar 100%.

Si algo de acá falla, es un bug real en la lógica determinista de `tools/`
o una expectativa mal calibrada en el golden set -- no un flake, no un
umbral a relajar (ver `evaluation/metrics.py`).
"""

from __future__ import annotations

from portfolio_intel.evaluation.golden_set import load_golden_set
from portfolio_intel.evaluation.metrics import pass_rate, run_golden_set


def test_golden_set_passes_completely(use_cases_df):
    golden_set = load_golden_set()
    results = run_golden_set(golden_set, use_cases_df)
    failed = [r for r in results if not r["passed"]]
    assert not failed, f"checks fallidos: {failed}"
    assert pass_rate(results) == 1.0
