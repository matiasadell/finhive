"""Top-level supervisor: compone los 4 agentes de dominio de Portfolio Intel.

Mismo patrón de fondo que finhive (`docs/architecture/adr/finhive-legacy/`,
ADR 0005/0006), con una diferencia deliberada documentada en
`docs/architecture/adr/0001-un-nivel-menos-de-jerarquia.md`: acá el
supervisor raíz rutea directo a un agente ReAct por dominio (sin un
sub-supervisor propio por equipo en el medio) -- un nivel menos de
jerarquía que finhive, elegido por el presupuesto de tiempo del hackathon
(ver `prompts/constraints_tech_stack.md`).

Los 4 dominios: `prioritization`, `reuse_duplication`, `value_realization`,
`portfolio_recommendation`. Sumar un dominio nuevo es: (1) construir su
agente igual que `agents.prioritization`, (2) sumarlo a `_TEAM_BUILDERS` y
`_TEAM_DESCRIPTIONS` acá abajo.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import pandas as pd
from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph
from langgraph.types import Command

from portfolio_intel.config.settings import get_chat_model
from portfolio_intel.data.store import load_portfolio_data
from portfolio_intel.graph.state import PortfolioState
from portfolio_intel.guardrails.input_guardrail import input_guardrail_node
from portfolio_intel.guardrails.output_guardrail import output_guardrail_node

_TEAM_DESCRIPTIONS = {
    "prioritization": (
        "qué casos de uso priorizar / escalar primero dado presupuesto limitado -- "
        "ranking por priority_score (impacto, eficiencia de inversión, confianza, "
        "stage, escalabilidad)"
    ),
    "reuse_duplication": (
        "qué casos de uso se solapan o son duplicados/redundantes entre sí -- "
        "oportunidades de reuso/consolidación"
    ),
    "value_realization": (
        "qué casos de uso YA APROBADOS no están en camino de realizar el valor "
        "prometido (sobre-costo, timeline vencida, barreras documentadas)"
    ),
    "portfolio_recommendation": (
        "la recomendación final por caso (Scale / Consolidate / Reduce Investment / "
        "Discontinue / Continue-Monitor) o un pedido de reporte ejecutivo general del "
        "portfolio -- compone las otras tres áreas, usar para preguntas amplias tipo "
        "'qué hacemos con el portfolio' o pedidos de síntesis final"
    ),
}


def _build_team_agents(df: pd.DataFrame) -> dict:
    from portfolio_intel.agents.portfolio_recommendation import build_portfolio_recommendation_agent
    from portfolio_intel.agents.prioritization import build_prioritization_agent
    from portfolio_intel.agents.reuse_duplication import build_reuse_duplication_agent
    from portfolio_intel.agents.value_realization import build_value_realization_agent

    return {
        "prioritization": build_prioritization_agent(df),
        "reuse_duplication": build_reuse_duplication_agent(df),
        "value_realization": build_value_realization_agent(df),
        "portfolio_recommendation": build_portfolio_recommendation_agent(df),
    }


class _Router(TypedDict):
    """Próximo agente a invocar. FINISH si ya no hace falta ninguno.

    `next` es `str`, no `Literal[*options]` -- mismo bug conocido de
    `with_structured_output` + `Literal` construido en runtime que ya
    documentó finhive (ver ADR 0005 archivada); se valida `next` contra
    `options` en código.
    """

    next: str


_MAX_ITERATIONS = 3


def _make_supervisor_node(members: list[str]):
    """Nodo supervisor: decide, vía structured output, a qué agente rutear."""
    options = ["FINISH", *members]
    team_lines = "\n".join(f"- {m}: {_TEAM_DESCRIPTIONS.get(m, '')}" for m in members)
    system_prompt = (
        "Sos el supervisor raíz de Portfolio Intel, un sistema de inteligencia "
        "de portfolio de IA para leadership de una aseguradora. Coordinás estos "
        f"agentes:\n{team_lines}\n\n"
        f"Dado el pedido del usuario, respondé con next = uno de {options} — el "
        "agente que tiene que actuar a continuación, o FINISH si la pregunta ya "
        "está completamente respondida. Fijate bien en las descripciones de "
        "arriba para elegir el agente correcto, sobre todo en preguntas de "
        "frontera. Cada agente responde con datos reales calculados por sus "
        "tools (no inventés vos ningún dato ni score). Si el último mensaje de "
        "un agente ya contesta la pregunta original del usuario, respondé "
        "FINISH inmediatamente -- no vuelvas a consultar al mismo agente sobre "
        "algo que ya respondió, ni a ningún otro. Este es un sistema de "
        "research/decisión de negocio, no ejecución real de inversión."
    )

    llm = get_chat_model("supervisor")
    structured_llm = llm.with_structured_output(_Router)

    def supervisor_node(state: PortfolioState) -> Command[Literal[*members, "output_guardrail"]]:
        iterations = state.get("iterations", 0)
        if iterations >= _MAX_ITERATIONS:
            return Command(goto="output_guardrail", update={"next": "FINISH"})

        messages = [{"role": "system", "content": system_prompt}] + state["messages"]
        response = structured_llm.invoke(messages)
        goto = response["next"] if response["next"] in options else members[0]
        if goto == "FINISH":
            return Command(goto="output_guardrail", update={"next": "FINISH"})
        return Command(goto=goto, update={"next": goto, "iterations": iterations + 1})

    return supervisor_node


def _make_team_node(team: str, agent):
    """Nodo que invoca un agente de dominio y vuelve al supervisor raíz.

    A diferencia de finhive, `agent` acá es directamente el ReAct agent del
    dominio (sin un sub-supervisor propio en el medio) -- ver el docstring
    del módulo.
    """

    def team_node(state: PortfolioState) -> Command[Literal["supervisor"]]:
        response = agent.invoke({"messages": state["messages"]})
        return Command(
            update={
                "messages": [
                    HumanMessage(content=response["messages"][-1].content, name=f"{team}_agent")
                ]
            },
            goto="supervisor",
        )

    return team_node


def build_top_supervisor(df: pd.DataFrame | None = None):
    """Compila el grafo jerárquico completo de Portfolio Intel.

    `df` es el snapshot del portfolio para esta invocación -- si no se pasa,
    se carga vía `data.store.load_portfolio_data()` (backend local o
    Databricks según `PORTFOLIO_INTEL_DATA_BACKEND`, ver
    `prompts/constraints_data.md`). Pasarlo explícito es lo que usan los
    tests estructurales (Task 14) para fijar un dataset conocido sin
    depender del backend real.

    Flujo: `START -> input_guardrail -> supervisor -> (agentes) -> supervisor
    -> ... -> output_guardrail -> END`. Sin nodos de memoria (a diferencia de
    finhive) -- no hay memoria persistente en este proyecto, ver
    `prompts/non_goals.md`.
    """
    df = df if df is not None else load_portfolio_data().get_use_cases()
    team_agents = _build_team_agents(df)
    members = list(team_agents.keys())

    builder = StateGraph(PortfolioState)
    builder.add_node("input_guardrail", input_guardrail_node)
    builder.add_node("supervisor", _make_supervisor_node(members))
    for team, agent in team_agents.items():
        builder.add_node(team, _make_team_node(team, agent))
    builder.add_node("output_guardrail", output_guardrail_node)
    builder.add_edge(START, "input_guardrail")
    return builder.compile()
