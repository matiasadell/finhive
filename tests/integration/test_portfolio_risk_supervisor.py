"""Smoke test end-to-end del sub-supervisor de Portfolio & Risk.

Pega contra Databricks real y yfinance real — no es un test unitario ni
corre en CI. Correr a mano con:

    uv run pytest tests/integration/test_portfolio_risk_supervisor.py -v -s

Requiere `.env` completo y la CLI de Databricks autenticada.
"""

from __future__ import annotations

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_portfolio_risk_supervisor_responds_with_grounded_data():
    mlflow.langchain.autolog()

    from finhive.agents.portfolio_risk import build_portfolio_risk_supervisor

    graph = build_portfolio_risk_supervisor()
    result = graph.invoke(
        {
            "messages": [
                (
                    "user",
                    "¿Cuál es la volatilidad anualizada de un portfolio 50% AAPL y 50% MSFT en los últimos 6 meses?",
                )
            ]
        }
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el supervisor no devolvió contenido"

    tool_messages = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    volatility_calls = [
        m for m in tool_messages if "volatilidad" in str(getattr(m, "content", "")).lower()
    ]
    assert volatility_calls, (
        "el supervisor respondió sin evidencia de haber llamado a la tool de "
        "volatilidad — probablemente alucinó el dato en vez de calcularlo"
    )
