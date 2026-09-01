"""Tests estructurales del grafo -- sin red, sin LLM real.

A diferencia de `test_live_agents.py` (marcado `live`, corre solo en la
compu de trabajo con Databricks real), esto corre en cualquier lado con
`langgraph`/`langchain` instalados (ver
`prompts/constraints_environment.md` y `CLAUDE.md` -- en esta máquina de
desarrollo, con el intérprete del entorno conda `portfolio_intel`, no con
el `python` de 3.14 del PATH).

Cubre el control de flujo del grafo (`Command(goto=...)` de los guardrails
y el router del supervisor) con un chat model fake
(`fake_get_chat_model_factory`, `tests/conftest.py`) -- no simula el
tool-calling interno de `create_agent` (eso es responsabilidad de
LangChain, no de este proyecto), así que `build_top_supervisor()` se
verifica hasta donde puede sin red: compila, y al invocarlo falla en el
primer punto que sí necesita un LLM real, con un error de
autenticación/conexión reconocible -- no un traceback de un bug de wiring.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from portfolio_intel.graph.state import PortfolioState
from portfolio_intel.graph.top_supervisor import _make_supervisor_node, build_top_supervisor
from portfolio_intel.guardrails.input_guardrail import input_guardrail_node
from portfolio_intel.guardrails.output_guardrail import output_guardrail_node


def _state(messages) -> PortfolioState:
    """Arma un `PortfolioState` con mensajes reales (`HumanMessage`/`AIMessage`),
    no las tuplas `(role, content)` que sí acepta `graph.invoke()` -- esas
    solo se normalizan a mensajes reales vía el reducer `add_messages` de
    LangGraph cuando pasan por el grafo completo; llamando a un nodo directo
    (como acá) hay que armarlos a mano."""
    real_messages = [
        HumanMessage(content=content) if role == "user" else AIMessage(content=content)
        for role, content in messages
    ]
    return {"messages": real_messages, "iterations": 0}


def test_input_guardrail_lets_in_scope_question_through(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.guardrails.input_guardrail.get_chat_model",
        fake_get_chat_model_factory({"in_scope": "si", "reason": "pregunta de portfolio"}),
    )
    result = input_guardrail_node(_state([("user", "¿Qué casos de uso priorizamos?")]))
    assert isinstance(result, Command)
    assert result.goto == "supervisor"


def test_input_guardrail_blocks_out_of_scope_question(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.guardrails.input_guardrail.get_chat_model",
        fake_get_chat_model_factory({"in_scope": "no", "reason": "no es sobre el portfolio de IA"}),
    )
    result = input_guardrail_node(_state([("user", "Escribime un poema sobre gatos.")]))
    assert isinstance(result, Command)
    assert result.goto == "__end__"
    assert result.update["messages"][0].name == "input_guardrail"


def test_output_guardrail_passes_grounded_answer(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.guardrails.output_guardrail.get_chat_model",
        fake_get_chat_model_factory({"grounded": "si", "reason": ""}),
    )
    result = output_guardrail_node(_state([("assistant", "UC-006 tiene priority_score 97.0")]))
    assert result.goto == "__end__"
    assert result.update is None


def test_output_guardrail_flags_ungrounded_answer(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.guardrails.output_guardrail.get_chat_model",
        fake_get_chat_model_factory({"grounded": "no", "reason": "cifra sin evidencia de tools"}),
    )
    result = output_guardrail_node(_state([("assistant", "UC-999 tiene un score inventado")]))
    assert result.goto == "__end__"
    warned = result.update["messages"][0]
    assert warned.name == "output_guardrail"
    assert "verificación automática" in warned.content
    assert "UC-999 tiene un score inventado" in warned.content  # respuesta original preservada


def test_supervisor_node_routes_to_named_agent(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.graph.top_supervisor.get_chat_model",
        fake_get_chat_model_factory({"next": "prioritization"}),
    )
    node = _make_supervisor_node(["prioritization", "reuse_duplication"])
    result = node(_state([("user", "¿Qué priorizamos?")]))
    assert result.goto == "prioritization"
    assert result.update["iterations"] == 1


def test_supervisor_node_finishes(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.graph.top_supervisor.get_chat_model",
        fake_get_chat_model_factory({"next": "FINISH"}),
    )
    node = _make_supervisor_node(["prioritization", "reuse_duplication"])
    result = node(_state([("user", "¿Qué priorizamos?"), ("assistant", "UC-006, ya respondido.")]))
    assert result.goto == "output_guardrail"


def test_supervisor_node_hits_max_iterations_safety_cap(monkeypatch, fake_get_chat_model_factory):
    monkeypatch.setattr(
        "portfolio_intel.graph.top_supervisor.get_chat_model",
        fake_get_chat_model_factory({"next": "prioritization"}),  # seguiría eligiendo el mismo
    )
    node = _make_supervisor_node(["prioritization", "reuse_duplication"])
    state = _state([("user", "¿Qué priorizamos?")])
    state["iterations"] = 3  # ya en el límite (_MAX_ITERATIONS = 3)
    result = node(state)
    assert result.goto == "output_guardrail"
    assert result.update["next"] == "FINISH"


def test_build_top_supervisor_compiles_without_network(use_cases_df):
    graph = build_top_supervisor(use_cases_df)
    assert graph is not None


def test_graph_invoke_fails_at_llm_boundary_not_earlier(use_cases_df):
    """Sin conexión a Databricks, invocar el grafo real tiene que fallar en
    la llamada al LLM (auth/conexión) -- no antes, por un bug de wiring."""
    graph = build_top_supervisor(use_cases_df)
    try:
        graph.invoke({"messages": [("user", "¿Qué priorizamos?")]})
        raise AssertionError(
            "se esperaba que fallara sin conexión a Databricks -- si esto "
            "pasó, hay conexión real disponible; correr los tests `live` en "
            "vez de este."
        )
    except Exception as e:  # noqa: BLE001 - a propósito, ver docstring
        message = str(e).lower()
        assert any(
            keyword in message
            for keyword in ("auth", "credential", "connection", "databricks", "token")
        ), f"falló con un error inesperado (no de auth/conexión): {type(e).__name__}: {e}"
