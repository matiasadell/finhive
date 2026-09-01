"""Carga el golden set de evaluación (`data/eval/golden_set.json`).

`data/eval/golden_set.json` es la fuente de verdad única, versionada en git
-- cada entrada nombra un `use case id` concreto del dataset sintético (ver
`data/sample_docs/README.md`) y qué señal determinista se espera de él
(duplicado, top priority, value_status, o acción recomendada). Ver
`metrics.py` para cómo se evalúa cada `check`.
"""

from __future__ import annotations

import json
from pathlib import Path

_GOLDEN_SET_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "golden_set.json"


def load_golden_set() -> list[dict]:
    """Lee `data/eval/golden_set.json`."""
    with _GOLDEN_SET_PATH.open(encoding="utf-8") as f:
        return json.load(f)
