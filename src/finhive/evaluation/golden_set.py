"""Carga el dataset dorado de evaluación (`data/eval/golden_set.json`).

Fuente de verdad única, versionada en git — se pasa directo como `data` a
`mlflow.genai.evaluate()` (ver `run_eval.py`), sin un paso previo de registro
en ningún sistema aparte (ADR 0014 — antes se subía también a LangSmith).
"""

from __future__ import annotations

import json
from pathlib import Path

_GOLDEN_SET_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "golden_set.json"


def load_golden_set() -> list[dict]:
    """Lee `data/eval/golden_set.json`: lista de {id, question, category, expected_teams}."""
    with _GOLDEN_SET_PATH.open(encoding="utf-8") as f:
        return json.load(f)
