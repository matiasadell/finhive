"""Smoke test end-to-end del sub-supervisor de News & Sentiment.

Pega contra Databricks real y Alpha Vantage real — no es un test unitario ni
corre en CI. Ojo: Alpha Vantage tiene free tier chico (~25 requests/día),
no correr este test en loop. Correr a mano con:

    uv run pytest tests/integration/test_news_sentiment_supervisor.py -v -s

Requiere `.env` completo (ALPHA_VANTAGE_API_KEY) y la CLI de Databricks
autenticada.
"""

from __future__ import annotations

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_news_sentiment_supervisor_responds_with_grounded_data():
    mlflow.langchain.autolog()

    from finhive.agents.news_sentiment import build_news_sentiment_supervisor

    graph = build_news_sentiment_supervisor()
    result = graph.invoke(
        {"messages": [("user", "¿Cuándo es el próximo reporte de earnings de Apple (AAPL)?")]}
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el supervisor no devolvió contenido"

    tool_messages = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    calendar_calls = [
        m for m in tool_messages if "earnings" in str(getattr(m, "content", "")).lower()
    ]
    assert calendar_calls, (
        "el supervisor respondió sin evidencia de haber llamado a la tool de "
        "calendario de earnings — probablemente alucinó la fecha en vez de "
        "consultarla"
    )
