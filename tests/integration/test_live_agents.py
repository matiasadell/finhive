"""Smoke tests end-to-end contra el grafo real, con LLM real vía Databricks.

Marcados `live`: no corren en esta máquina de desarrollo (no hay conexión a
Databricks, ver `prompts/constraints_environment.md`) -- correr a mano en la
compu de trabajo, con `.env` completo y `databricks auth login` hecho:

    pytest tests/integration/test_live_agents.py -v -s -m live

Sin el flag `-m live`, `pyproject.toml` los deselecciona por default (ver
`[tool.pytest.ini_options]`) -- así `pytest` sin argumentos nunca falla acá
por falta de conexión, en vez de fallar silenciosamente sin explicar por qué.
"""

from __future__ import annotations

import pytest

from portfolio_intel.data.store import load_portfolio_data
from portfolio_intel.graph.top_supervisor import build_top_supervisor


@pytest.mark.live
def test_prioritization_question_routes_and_answers():
    df = load_portfolio_data().get_use_cases()
    graph = build_top_supervisor(df)
    result = graph.invoke(
        {"messages": [("user", "¿Qué casos de uso deberíamos priorizar este trimestre?")]}
    )
    final_message = result["messages"][-1]
    assert final_message.content

    agent_messages = [
        m for m in result["messages"] if getattr(m, "name", None) == "prioritization_agent"
    ]
    assert agent_messages, "se esperaba que el supervisor delegara a prioritization_agent"


@pytest.mark.live
def test_offtopic_question_blocked_by_input_guardrail():
    df = load_portfolio_data().get_use_cases()
    graph = build_top_supervisor(df)
    result = graph.invoke({"messages": [("user", "Escribime un poema corto sobre gatos.")]})
    final_message = result["messages"][-1]
    assert getattr(final_message, "name", None) == "input_guardrail"


@pytest.mark.live
def test_executive_recommendation_question_reaches_recommendation_agent():
    df = load_portfolio_data().get_use_cases()
    graph = build_top_supervisor(df)
    result = graph.invoke(
        {
            "messages": [
                (
                    "user",
                    "Dame la recomendación completa del portfolio: qué escalar, "
                    "consolidar, reducir o discontinuar.",
                )
            ]
        }
    )
    agent_messages = [
        m
        for m in result["messages"]
        if getattr(m, "name", None) == "portfolio_recommendation_agent"
    ]
    assert agent_messages, "se esperaba que el supervisor delegara a portfolio_recommendation_agent"
