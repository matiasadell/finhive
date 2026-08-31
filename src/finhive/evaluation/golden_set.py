"""Carga el dataset dorado de evaluación (`data/eval/golden_set.json`).

`data/eval/golden_set.json` sigue siendo la fuente de verdad única,
versionada en git (ADR 0013/0014) — nunca se edita desde ningún sistema
externo. `sync_uc_dataset()` lo sincroniza hacia un `EvaluationDataset` de
MLflow en Unity Catalog (ADR 0016): mismo criterio que ya usaba
`_ensure_dataset` con LangSmith en la versión original de esto (ADR 0013),
adaptado al reemplazo de ese sistema por evaluación nativa de MLflow (ADR
0014) — se sube una copia sincronizada, no se convierte a la UC en la fuente
de verdad, para no arriesgar que diverja de lo versionado en git.
"""

from __future__ import annotations

import json
from pathlib import Path

from finhive.config.settings import UC_CATALOG, UC_SCHEMA

_GOLDEN_SET_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "golden_set.json"
UC_DATASET_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.golden_set"


def load_golden_set() -> list[dict]:
    """Lee `data/eval/golden_set.json`: lista de {id, question, category, expected_teams}."""
    with _GOLDEN_SET_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def sync_uc_dataset(golden_set: list[dict], experiment_id: str | None = None):
    """Sincroniza el dataset dorado hacia un `EvaluationDataset` de MLflow en UC.

    Da versionado y trazabilidad de lineage (qué corrida de evaluación usó
    qué versión del dataset) que un `data/eval/golden_set.json` suelto no
    tiene. `merge_records` es idempotente: un registro con el mismo `inputs`
    actualiza sus `expectations`/tags en vez de duplicarse, así que se puede
    llamar en cada corrida de `run_eval.py` sin acumular basura.
    """
    from databricks.sdk.errors import NotFound
    from mlflow.exceptions import MlflowException
    from mlflow.genai.datasets import create_dataset, get_dataset

    try:
        dataset = get_dataset(name=UC_DATASET_NAME)
    # `get_dataset` deja pasar el NotFound del SDK de Databricks sin
    # envolverlo en un MlflowException -- confirmado en vivo (ADR 0016), no
    # documentado. Se atrapan los dos para no depender de un detalle interno
    # que podría cambiar entre versiones.
    except (NotFound, MlflowException):
        dataset = create_dataset(name=UC_DATASET_NAME, experiment_id=experiment_id)

    records = [
        {
            "inputs": {"question": item["question"]},
            "expectations": {"expected_teams": item["expected_teams"]},
            "tags": {"id": item["id"], "category": item["category"]},
        }
        for item in golden_set
    ]
    dataset.merge_records(records)
    return dataset
