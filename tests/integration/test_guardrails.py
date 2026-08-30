"""Smoke tests de los guardrails de entrada y salida del grafo jerárquico.

Pega contra Databricks real (mismo caveat de rate limiting que el resto de
`tests/integration/`). Correr a mano con:

    uv run pytest tests/integration/test_guardrails.py -v -s

Requiere `.env` completo y la CLI de Databricks autenticada.
"""

from __future__ import annotations

import uuid

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_input_guardrail_blocks_offtopic_request():
    mlflow.langchain.autolog()

    from finhive.graph import build_top_supervisor

    graph = build_top_supervisor()
    # thread_id propio: desde que `memory_recall` corre antes que
    # `input_guardrail` (ADR 0013), un thread compartido/reusado traería
    # mensajes de equipo de turnos anteriores de OTRO test, y la aserción de
    # abajo (ningún equipo invocado) daría falso negativo por ruido ajeno,
    # no por un bug real.
    config = {"configurable": {"thread_id": f"test-offtopic-{uuid.uuid4()}"}}
    result = graph.invoke(
        {"messages": [("user", "Escribime un poema corto sobre gatos.")]},
        config=config,
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el guardrail de entrada no devolvió ningún mensaje"
    assert getattr(final_message, "name", None) == "input_guardrail", (
        "se esperaba que el pedido fuera bloqueado por input_guardrail antes "
        "de llegar al supervisor raíz"
    )

    team_messages = [
        m
        for m in result["messages"]
        if getattr(m, "name", None) and str(m.name).endswith("_team")
    ]
    assert not team_messages, (
        "un pedido fuera de scope no debería haber delegado a ningún equipo "
        "de dominio — el guardrail de entrada tiene que cortar antes"
    )


@pytest.mark.integration
def test_financial_question_passes_both_guardrails():
    mlflow.langchain.autolog()

    from finhive.graph import build_top_supervisor

    graph = build_top_supervisor()
    config = {"configurable": {"thread_id": f"test-financial-{uuid.uuid4()}"}}
    result = graph.invoke(
        {
            "messages": [
                (
                    "user",
                    "¿Cuál es el precio actual de Bitcoin y cómo viene su tendencia reciente?",
                )
            ]
        },
        config=config,
    )

    final_message = result["messages"][-1]
    assert final_message.content, "el sistema no devolvió ninguna respuesta final"
    assert getattr(final_message, "name", None) != "input_guardrail", (
        "una pregunta financiera legítima no debería ser bloqueada por el "
        "guardrail de entrada"
    )

    team_messages = [
        m
        for m in result["messages"]
        if getattr(m, "name", None) and str(m.name).endswith("_team")
    ]
    assert team_messages, (
        "se esperaba que el pedido pasara el guardrail de entrada y llegara "
        "a delegarse en al menos un equipo de dominio (crypto_alt)"
    )
