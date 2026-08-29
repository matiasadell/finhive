"""Smoke test end-to-end del sub-supervisor de Crypto & Alt.

Pega contra Databricks real y CoinGecko real (API pública, sin key, pero con
rate limiting agresivo bajo uso intensivo) — no es un test unitario ni corre
en CI. Correr a mano con:

    uv run pytest tests/integration/test_crypto_alt_supervisor.py -v -s

Requiere la CLI de Databricks autenticada (no necesita ninguna key para
CoinGecko).
"""

from __future__ import annotations

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_crypto_alt_supervisor_responds_with_grounded_data():
    mlflow.langchain.autolog()

    from finhive.agents.crypto_alt import build_crypto_alt_supervisor

    graph = build_crypto_alt_supervisor()
    result = graph.invoke({"messages": [("user", "¿Cuál es el precio actual de Bitcoin?")]})

    final_message = result["messages"][-1]
    assert final_message.content, "el supervisor no devolvió contenido"

    tool_messages = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    price_calls = [
        m for m in tool_messages if "precio actual" in str(getattr(m, "content", "")).lower()
    ]
    assert price_calls, (
        "el supervisor respondió sin evidencia de haber llamado a la tool de "
        "precio de cripto — probablemente alucinó el dato en vez de consultarlo"
    )
