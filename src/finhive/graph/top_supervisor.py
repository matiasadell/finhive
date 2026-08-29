"""Top-level supervisor: compone los sub-supervisores de dominio.

Mismo patrón que "Hierarchical Agent Teams" en el notebook de referencia del
bootcamp: cada equipo de dominio es un subgrafo compilado, invocado desde un
nodo del grafo superior; el supervisor raíz decide, con structured output, a
qué equipo rutear cada turno, hasta que decide FINISH.

Equipos reales hoy: `macro`, `equity`, `portfolio_risk`, `news_sentiment`.
Agregar crypto_alt es: (1) construir su sub-supervisor igual que
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

# Descripción corta de cada equipo, usada en el prompt del router para
# desambiguar preguntas de frontera (ver comentario en _make_supervisor_node
# sobre el bug de ruteo entre equity/news_sentiment que motivó esto).
_TEAM_DESCRIPTIONS = {}


def _register_macro_team() -> None:
    from finhive.agents.macro import build_macro_supervisor

    _TEAM_BUILDERS["macro"] = build_macro_supervisor
    _TEAM_DESCRIPTIONS["macro"] = (
        "política monetaria, tasas de interés, inflación, indicadores macro (FRED)"
    )


def _register_equity_team() -> None:
    from finhive.agents.equity import build_equity_supervisor

    _TEAM_BUILDERS["equity"] = build_equity_supervisor
    _TEAM_DESCRIPTIONS["equity"] = (
        "fundamentals, valuación (P/E, EPS), análisis técnico y filings YA "
        "REPORTADOS de una empresa (10-K/10-Q pasados). NO calendario de "
        "próximos earnings — eso es news_sentiment."
    )


def _register_portfolio_risk_team() -> None:
    from finhive.agents.portfolio_risk import build_portfolio_risk_supervisor

    _TEAM_BUILDERS["portfolio_risk"] = build_portfolio_risk_supervisor
    _TEAM_DESCRIPTIONS["portfolio_risk"] = (
        "volatilidad, VaR, correlación y Sharpe ratio de un portfolio de acciones"
    )


def _register_news_sentiment_team() -> None:
    from finhive.agents.news_sentiment import build_news_sentiment_supervisor

    _TEAM_BUILDERS["news_sentiment"] = build_news_sentiment_supervisor
    _TEAM_DESCRIPTIONS["news_sentiment"] = (
        "noticias, sentimiento de mercado, y calendario de PRÓXIMOS earnings/"
        "eventos corporativos (fechas futuras, no resultados ya reportados)"
    )


_register_macro_team()
_register_equity_team()
_register_portfolio_risk_team()
_register_news_sentiment_team()

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
    """Nodo supervisor: decide, vía structured output, a qué equipo rutear.

    Se probó originalmente pasándole al router solo los *nombres* de los
    equipos (sin descripción). Resultado: "¿cuándo es el próximo earnings de
    Apple?" se ruteó a `equity` en vez de `news_sentiment` — equity no tiene
    la tool de calendario, y terminó alucinando una fecha (dijo 2025, la
    real era 2026) en vez de admitir que no tenía el dato. Se agregaron
    descripciones por equipo, con líneas explícitas de "esto NO es de este
    equipo" en los casos de frontera conocidos, para desambiguar.
    """
    options = ["FINISH", *members]
    team_lines = "\n".join(f"- {m}: {_TEAM_DESCRIPTIONS.get(m, '')}" for m in members)
    system_prompt = (
        "Sos el supervisor raíz de FinHive, un sistema de análisis financiero "
        f"multiagente. Coordinás estos equipos de dominio:\n{team_lines}\n\n"
        f"Dado el pedido del usuario, respondé con next = uno de {options} — "
        "el equipo que tiene que actuar a continuación, o FINISH si la "
        "pregunta ya está completamente respondida. Fijate bien en las "
        "descripciones de arriba para elegir el equipo correcto, sobre todo "
        "en preguntas de frontera. Cada equipo hace su análisis y responde "
        "con resultados reales (no inventés vos ningún dato). Si el último "
        "mensaje de un equipo ya contesta la pregunta original del usuario, "
        "respondé FINISH inmediatamente — no vuelvas a consultar al mismo "
        "equipo sobre algo que ya respondió. Este es un sistema de research, "
        "no de asesoramiento financiero."
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
