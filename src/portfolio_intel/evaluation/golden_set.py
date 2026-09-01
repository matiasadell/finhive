from __future__ import annotations

import json
from pathlib import Path

_GOLDEN_SET_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "golden_set.json"


def load_golden_set() -> list[dict]:
    with _GOLDEN_SET_PATH.open(encoding="utf-8") as f:
        return json.load(f)
