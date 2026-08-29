"""Smoke test end-to-end del sub-supervisor de Equity Research.

Pega contra Databricks real, yfinance y SEC EDGAR reales — no es un test
unitario ni corre en CI. Correr a mano con:

    uv run pytest tests/integration/test_equity_supervisor.py -v -s

Requiere `.env` completo (SEC_EDGAR_USER_AGENT, DATABRICKS_CONFIG_PROFILE) y
la CLI de Databricks autenticada (`databricks auth login`).
"""

from __future__ import annotations

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_equity_supervisor_responds_with_grounded_data():
    mlflow.langchain.autolog()

    from finhive.agents.equity import build_equity_supervisor

    graph = build_equity_supervisor()
    result = graph.invoke(
        {"messages": [("user", "¿Cuál es el P/E actual de Apple (AAPL)?")]}
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el supervisor no devolvió contenido"

    tool_messages = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    data_calls = [
        m
        for m in tool_messages
        if "P/E" in str(getattr(m, "content", "")) or "AAPL" in str(getattr(m, "content", ""))
    ]
    assert data_calls, (
        "el supervisor respondió sin evidencia de haber llamado a una tool de "
        "datos de equity — probablemente alucinó el dato en vez de consultarlo"
    )
