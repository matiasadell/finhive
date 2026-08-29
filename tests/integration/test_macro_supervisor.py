"""Smoke test end-to-end del sub-supervisor de Macro.

Pega contra Databricks real (Llama 3.3 70B + 3.1 8B vía Model Serving) y
contra la API real de FRED — no es un test unitario ni corre en CI. Correr a
mano con:

    uv run pytest tests/integration/test_macro_supervisor.py -v -s

Requiere `.env` completo (FRED_API_KEY, DATABRICKS_CONFIG_PROFILE) y la CLI
de Databricks autenticada (`databricks auth login`).
"""

from __future__ import annotations

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_macro_supervisor_responds_with_grounded_data():
    mlflow.langchain.autolog()

    from finhive.agents.macro import build_macro_supervisor

    graph = build_macro_supervisor()
    result = graph.invoke(
        {
            "messages": [
                ("user", "¿Cuál es la tasa de fondos federales (FEDFUNDS) actual, según FRED?")
            ]
        }
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el supervisor no devolvió contenido"

    tool_messages = [
        m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"
    ]
    fred_calls = [
        m
        for m in tool_messages
        if "series" in str(getattr(m, "content", "")).lower()
        or "fred" in str(getattr(m, "name", "")).lower()
    ]
    assert fred_calls, (
        "el supervisor respondió sin evidencia de haber llamado a una tool de "
        "FRED — probablemente alucinó el dato en vez de consultarlo"
    )
