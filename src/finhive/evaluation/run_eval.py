"""Corre el dataset dorado contra el grafo completo; loguea a LangSmith y MLflow.

El grafo corre UNA vez por pregunta — no dos: `langsmith.evaluate()` invoca
`target()` (que llama a `build_top_supervisor().invoke(...)`) como parte de
su propio harness, y los mismos resultados que produce esa corrida son los
que se resumen y suben a MLflow después. Ver ADR 0013.

Uso:
    uv run python -m finhive.evaluation.run_eval

Requiere `.env` completo (incluye `LANGSMITH_API_KEY`), la CLI de Databricks
autenticada, y que `data/eval/golden_set.json` exista (ya versionado en git).
"""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from pathlib import Path

import mlflow
from langsmith import Client, evaluate

from finhive.config.settings import get_databricks_workspace_email
from finhive.evaluation.golden_set import load_golden_set
from finhive.evaluation.metrics import (
    groundedness_evaluator,
    latency_evaluator,
    routing_accuracy_evaluator,
)

_DATASET_NAME = "finhive-golden-set"


def _log_results_table(df) -> None:
    """Loguea los resultados como artifact JSON, sin pasar por `mlflow.log_table`.

    `mlflow.log_table` serializa con el backend `ujson` de pandas, que se
    rompe con `OverflowError: Unterminated UTF-8 sequence` ante texto real
    de este dataset (probable objeto anidado que `to_pandas()` de LangSmith
    deja en alguna columna de feedback, no un `str` plano — una limpieza de
    caracteres célula por célula no alcanzó a evitarlo, se probó primero).
    `json.dumps(default=str, ensure_ascii=True)` es a prueba de balas contra
    esto: cualquier objeto no serializable cae a `str()`, y con
    `ensure_ascii=True` el archivo final es ASCII puro, imposible de dejar
    una secuencia UTF-8 mal formada al escribirlo. Se detectó corriendo el
    dataset dorado completo dos veces — ver ADR 0013.
    """
    payload = json.dumps(df.to_dict(orient="records"), default=str, ensure_ascii=True, indent=2)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "eval_results.json"
        tmp_path.write_text(payload, encoding="utf-8")
        mlflow.log_artifact(str(tmp_path))


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from finhive.graph import build_top_supervisor

        _graph = build_top_supervisor()
    return _graph


def target(inputs: dict) -> dict:
    """Corre una pregunta del dataset contra el grafo completo; thread_id nuevo cada vez.

    Un `thread_id` fresco por pregunta evita que la memoria de sesión (ADR
    0012) mezcle el historial de una pregunta del dataset con otra — cada
    ejemplo se evalúa de forma independiente.
    """
    graph = _get_graph()
    thread_id = f"eval-{uuid.uuid4()}"

    start = time.perf_counter()
    result = graph.invoke(
        {"messages": [("user", inputs["question"])]},
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


def _ensure_dataset(client: Client, golden_set: list[dict]) -> None:
    """Crea el Dataset de LangSmith desde `golden_set.json` si todavía no existe."""
    if client.has_dataset(dataset_name=_DATASET_NAME):
        return

    client.create_dataset(
        dataset_name=_DATASET_NAME,
        description=(
            "Dataset dorado de FinHive: preguntas por dominio, cross-domain, "
            "fuera de scope y un caso límite conocido (ver ADR 0006/0013). "
            "Fuente de verdad: data/eval/golden_set.json en el repo."
        ),
    )
    client.create_examples(
        dataset_name=_DATASET_NAME,
        examples=[
            {
                "inputs": {"question": item["question"]},
                "outputs": {"expected_teams": item["expected_teams"]},
                "metadata": {"id": item["id"], "category": item["category"]},
            }
            for item in golden_set
        ],
    )


def main() -> None:
    golden_set = load_golden_set()
    client = Client()
    _ensure_dataset(client, golden_set)

    results = evaluate(
        target,
        data=_DATASET_NAME,
        evaluators=[routing_accuracy_evaluator, latency_evaluator, groundedness_evaluator],
        experiment_prefix="finhive-eval",
        # 1 a la vez: el tier supervisor del AI Gateway tiene rate limit de
        # 30 llamadas/usuario/min (ADR 0008) -- correr las 15 preguntas en
        # paralelo pegaría contra ese límite.
        max_concurrency=1,
    )
    df = results.to_pandas()

    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(f"/Users/{get_databricks_workspace_email()}/finhive-eval")

    with mlflow.start_run(run_name=f"finhive-eval-{uuid.uuid4().hex[:8]}"):
        mlflow.log_param("dataset", _DATASET_NAME)
        mlflow.log_param("num_examples", len(golden_set))
        mlflow.log_param("langsmith_experiment_url", results.url)

        routing_col = [c for c in df.columns if "routing_accuracy" in c]
        latency_col = [c for c in df.columns if "latency_seconds" in c]
        grounded_col = [c for c in df.columns if "groundedness" in c]
        if routing_col:
            mlflow.log_metric("routing_accuracy", df[routing_col[0]].mean())
        if latency_col:
            mlflow.log_metric("avg_latency_seconds", df[latency_col[0]].mean())
        if grounded_col:
            grounded_values = df[grounded_col[0]].dropna()
            if len(grounded_values):
                mlflow.log_metric("groundedness", grounded_values.mean())

        _log_results_table(df)

    print(f"LangSmith experiment: {results.url}")
    print(df)


if __name__ == "__main__":
    main()
