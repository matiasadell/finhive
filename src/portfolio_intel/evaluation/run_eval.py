"""Corre el dataset dorado contra el grafo completo; evalúa con MLflow GenAI nativo.

El grafo corre UNA vez por pregunta: `mlflow.genai.evaluate()` invoca
`predict_fn()` (que llama a `build_top_supervisor().invoke(...)`) internamente
por cada ejemplo del dataset, y aplica los scorers de `metrics.py` sobre esos
mismos resultados -- no hay una segunda corrida aparte. Migrado desde
`langsmith.evaluate()` (ver ADR 0013 para el diseño original, ADR 0014 para
la migración): ya no hace falta registrar el dataset dorado en ningún sistema
aparte, se pasa directo como `data`.

Uso:
    uv run python -m finhive.evaluation.run_eval

Requiere `.env` completo, la CLI de Databricks autenticada, y que
`data/eval/golden_set.json` exista (ya versionado en git).
"""

from __future__ import annotations

import os
import time
import uuid

import mlflow
import mlflow.langchain

# `mlflow.genai.evaluate()` corre `predict_fn` con hasta 10 preguntas en
# paralelo por default (`MLFLOW_GENAI_EVAL_MAX_WORKERS`, no expuesto como
# parámetro de la función, solo como env var). Verificado en vivo: con el
# default, 10 preguntas concurrentes × ~4 llamadas LLM cada una saturan el
# rate limit de 30 llamadas/usuario/min del tier supervisor (ADR 0008) más
# rápido de lo que el rate-limiter adaptativo de MLflow puede compensar —
# la corrida completa del dataset dorado terminó con `predict_fn` fallando
# (excepción de rate-limit sin atrapar, no cubierta por `safe_tool`, que
# solo envuelve tools de datos, no llamadas al LLM) en 14 de 15 preguntas.
# Mismo mecanismo, mismo fix que `max_concurrency=1` con `langsmith.evaluate()`
# (ver ADR 0013) — se fija en 1 antes de importar `mlflow.genai`.
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")

from finhive.evaluation.golden_set import load_golden_set, sync_uc_dataset
from finhive.evaluation.metrics import groundedness, latency, routing_accuracy

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from finhive.graph import build_top_supervisor

        _graph = build_top_supervisor()
    return _graph


@mlflow.trace
def predict_fn(question: str) -> dict:
    """Corre una pregunta del dataset contra el grafo completo; thread_id nuevo cada vez.

    Un `thread_id` fresco por pregunta evita que la memoria de sesión (ADR
    0012) mezcle el historial de una pregunta del dataset con otra -- cada
    ejemplo se evalúa de forma independiente. `mlflow.genai.evaluate()` pasa
    el valor de `inputs["question"]` acá como argumento nombrado (el nombre
    del parámetro tiene que matchear la clave de `inputs` en `_build_eval_data`).
    Decorado con `@mlflow.trace` para garantizar una única traza por llamada,
    como pide la documentación de `evaluate()` para funciones que no la emiten
    solas (acá sí la emite `mlflow.langchain.autolog()`, pero el decorador no
    tiene costo real y saca cualquier ambigüedad al respecto).
    """
    graph = _get_graph()
    thread_id = f"eval-{uuid.uuid4()}"

    start = time.perf_counter()
    result = graph.invoke(
        {"messages": [("user", question)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    latency_seconds = time.perf_counter() - start

    messages = result["messages"]
    final_message = messages[-1]
    blocked = getattr(final_message, "name", None) == "input_guardrail"
    team_messages = [
        m for m in messages if getattr(m, "name", None) and str(m.name).endswith("_team")
    ]
    actual_teams = sorted({m.name[: -len("_team")] for m in team_messages})
    team_evidence = "\n\n".join(f"[{m.name}]: {m.content}" for m in team_messages)

    return {
        "answer": str(final_message.content),
        "actual_teams": actual_teams,
        "blocked": blocked,
        "latency_seconds": round(latency_seconds, 2),
        "team_evidence": team_evidence,
    }


def main() -> None:
    golden_set = load_golden_set()

    mlflow.set_tracking_uri("databricks")
    mlflow.langchain.autolog()

    from finhive.config.settings import get_databricks_workspace_email

    experiment = mlflow.set_experiment(f"/Users/{get_databricks_workspace_email()}/finhive-eval")

    # `sync_uc_dataset` sube el dataset dorado a un EvaluationDataset de
    # Unity Catalog (ADR 0016) -- da versionado y lineage (qué corrida usó
    # qué versión del dataset) que un archivo JSON suelto no tiene.
    # `data/eval/golden_set.json` sigue siendo la fuente de verdad, esto es
    # una copia sincronizada, no un reemplazo (ver docstring de golden_set.py).
    dataset = sync_uc_dataset(golden_set, experiment_id=experiment.experiment_id)

    # `mlflow.genai.evaluate()` corre las filas de a una (no es thread-safe,
    # documentado explícitamente) -- respeta el rate limit de 30
    # llamadas/usuario/min del tier supervisor (ADR 0008) sin necesitar un
    # parámetro de concurrencia explícito como el `max_concurrency=1` que sí
    # hacía falta con `langsmith.evaluate()`.
    results = mlflow.genai.evaluate(
        predict_fn=predict_fn,
        data=dataset,
        scorers=[routing_accuracy, latency, groundedness],
    )

    df = results.tables["eval_results"]
    routing_mean = df["routing_accuracy/value"].mean()
    latency_mean = df["latency/value"].mean()
    grounded_values = df["groundedness/value"].dropna()
    groundedness_mean = grounded_values.mean() if len(grounded_values) else None

    print(f"routing_accuracy promedio: {routing_mean:.3f}")
    print(f"latencia promedio: {latency_mean:.2f}s")
    if groundedness_mean is not None:
        print(f"groundedness promedio: {groundedness_mean:.3f} (sobre {len(grounded_values)} preguntas de dominio)")
    else:
        print("groundedness: sin preguntas de dominio evaluadas")
    print(f"\nVer el detalle completo en el experimento de MLflow: /Users/{get_databricks_workspace_email()}/finhive-eval")


if __name__ == "__main__":
    main()
