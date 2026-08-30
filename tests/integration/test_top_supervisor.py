"""Smoke test end-to-end del grafo jerárquico completo (top-level supervisor).

Pega contra Databricks real. Sujeto a rate limiting de cuota del Free
Edition (`REQUEST_LIMIT_EXCEEDED`, HTTP 429) si se corre justo después de
otros tests — no es un error de facturación, es la cuota de requests/minuto.
Correr a mano con:

    uv run pytest tests/integration/test_top_supervisor.py -v -s

Requiere `.env` completo y la CLI de Databricks autenticada.
"""

from __future__ import annotations

import uuid

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_top_supervisor_routes_to_macro_team():
    mlflow.langchain.autolog()

    from finhive.graph import build_top_supervisor

    graph = build_top_supervisor()
    # thread_id propio para no leer/ensuciar la sesión "default" compartida
    # (memoria persistente, ADR 0012/0013) con otros tests o corridas.
    config = {"configurable": {"thread_id": f"test-top-supervisor-{uuid.uuid4()}"}}
    result = graph.invoke(
        {
            "messages": [
                (
                    "user",
                    "¿Cómo viene el crecimiento del PIB (GDP) en Estados Unidos según los datos más recientes?",
                )
            ]
        },
        config=config,
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el supervisor raíz no devolvió contenido"

    team_messages = [
        m
        for m in result["messages"]
        if getattr(m, "name", None) and str(m.name).endswith("_team")
    ]
    assert team_messages, (
        "el supervisor raíz respondió sin haber delegado a ningún equipo de "
        "dominio — se esperaba al menos una respuesta con name='macro_team'"
    )
