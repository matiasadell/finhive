"""Top-level supervisor: compone los sub-supervisores de dominio.

Mismo patrón que "Hierarchical Agent Teams" en el notebook de referencia del
bootcamp: cada equipo de dominio es un subgrafo compilado, invocado desde un
nodo del grafo superior; el supervisor raíz decide, con structured output, a
qué equipo rutear cada turno, hasta que decide FINISH.

Hoy solo hay un equipo real (`macro`); agregar equity/portfolio_risk/
news_sentiment/crypto_alt es: (1) construir su sub-supervisor igual que
`finhive.agents.macro`, (2) sumarlo a `_TEAM_BUILDERS` acá abajo. El resto
(routing, síntesis) ya generaliza solo.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from finhive.config.settings import get_chat_model
from finhive.graph.state import FinHiveState

# Cada entrada: nombre del equipo -> función que construye su grafo compilado.
# Se instancian de forma perezosa (lazy) y se cachean, para no pagar el costo
# de armar cada sub-supervisor hasta que efectivamente hace falta.
_TEAM_BUILDERS = {}


def _register_macro_team() -> None:
    from finhive.agents.macro import build_macro_supervisor

    _TEAM_BUILDERS["macro"] = build_macro_supervisor


_register_macro_team()

_team_graph_cache: dict[str, object] = {}


def _get_team_graph(team: str):
    if team not in _team_graph_cache:
        _team_graph_cache[team] = _TEAM_BUILDERS[team]()
    return _team_graph_cache[team]


class _Router(TypedDict):
    """Próximo equipo a invocar. FINISH si ya no hace falta ninguno.

    `next` es `str` a propósito, no `Literal[*options]`: un `Literal`
    construido en runtime con unpacking rompe la conversión a schema de
    `with_structured_output` en `databricks-langchain` (cae en un path viejo
    de pydantic v1 que no maneja bien ese caso — `TypeError: issubclass()
    arg 1 must be a class`). Se valida `next` contra `options` en código en
    vez de delegarlo al schema.
    """

    next: str


# Límite duro de vueltas supervisor→equipo→supervisor. Se observó en la
# práctica que el router seguía eligiendo el mismo equipo varias veces sobre
# una pregunta ya respondida en vez de decidir FINISH — este cap evita que
# eso se traduzca en gastar cuota de requests sin límite (ver state.py).
_MAX_ITERATIONS = 3


def _make_supervisor_node(members: list[str]):
    """Nodo supervisor: decide, vía structured output, a qué equipo rutear."""
    options = ["FINISH", *members]
    system_prompt = (
        "Sos el supervisor raíz de FinHive, un sistema de análisis financiero "
        f"multiagente. Coordinás estos equipos de dominio: {members}. Dado el "
        f"pedido del usuario, respondé con next = uno de {options} — el "
        "equipo que tiene que actuar a continuación, o FINISH si la pregunta "
        "ya está completamente respondida. Cada equipo hace su análisis y "
        "responde con resultados reales (no inventés vos ningún dato). Si el "
        "último mensaje de un equipo ya contesta la pregunta original del "
        "usuario, respondé FINISH inmediatamente — no vuelvas a consultar al "
        "mismo equipo sobre algo que ya respondió. Este es un sistema de "
        "research, no de asesoramiento financiero."
    )

    llm = get_chat_model("supervisor")
    structured_llm = llm.with_structured_output(_Router)

    def supervisor_node(state: FinHiveState) -> Command[Literal[*members, "__end__"]]:
        iterations = state.get("iterations", 0)
        if iterations >= _MAX_ITERATIONS:
            return Command(goto=END, update={"next": "FINISH"})

        messages = [{"role": "system", "content": system_prompt}] + state["messages"]
        response = structured_llm.invoke(messages)
        goto = response["next"] if response["next"] in options else members[0]
        if goto == "FINISH":
            return Command(goto=END, update={"next": "FINISH"})
        return Command(goto=goto, update={"next": goto, "iterations": iterations + 1})

    return supervisor_node


def _make_team_node(team: str):
    """Nodo que invoca un sub-supervisor de dominio y vuelve al supervisor raíz."""

    def team_node(state: FinHiveState) -> Command[Literal["supervisor"]]:
        graph = _get_team_graph(team)
        response = graph.invoke({"messages": state["messages"]})
        return Command(
            update={
                "messages": [
                    HumanMessage(content=response["messages"][-1].content, name=f"{team}_team")
                ]
            },
            goto="supervisor",
        )

    return team_node


def build_top_supervisor():
    """Compila el grafo jerárquico completo de FinHive."""
    members = list(_TEAM_BUILDERS.keys())

    builder = StateGraph(FinHiveState)
    builder.add_node("supervisor", _make_supervisor_node(members))
    for team in members:
        builder.add_node(team, _make_team_node(team))
    builder.add_edge(START, "supervisor")
    return builder.compile()
