"""Guardrail de salida: verifica grounding antes de entregar la respuesta final.

Corre una única vez, justo antes de terminar el grafo — tanto si el
supervisor raíz decidió FINISH como si se cortó por el límite de
iteraciones de `top_supervisor.py` (`_MAX_ITERATIONS`, el caso con más
riesgo real de una respuesta a medio construir). Ataca directamente los dos
bugs de alucinación reales documentados en este proyecto (ADR 0004: fallo
silencioso de `UCFunctionToolkit` en Windows → tasa de fondos federales
inventada; ADR 0006: pregunta ruteada al equipo equivocado → fecha de
earnings inventada): en ambos casos, el sistema devolvió una cifra o fecha
plausible en vez de admitir que no tenía el dato.

No reintenta ni corrige la respuesta (eso implicaría loopear de vuelta al
supervisor, con el consumo de cuota que eso trae) — solo la marca
explícitamente cuando no encuentra evidencia de tool calls reales que la
respalden, para que quien lea la respuesta sepa que no está verificada.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from langchain_core.messages import AIMessage
from langgraph.graph import END
from langgraph.types import Command

from finhive.config.settings import get_chat_model
from finhive.graph.state import FinHiveState

_SYSTEM_PROMPT = (
    "Sos el guardrail de salida de FinHive. Te paso el historial completo de "
    "una conversación de un sistema multiagente de research financiero, "
    "terminando en una respuesta final. Los mensajes de los equipos de "
    'dominio (etiquetados "<equipo>_team") son la ÚNICA evidencia real '
    "disponible — vienen de tools que consultaron APIs reales (FRED, "
    "yfinance, SEC EDGAR, Alpha Vantage, CoinGecko) o de cómputo propio "
    "sobre esos datos.\n\n"
    "Tu trabajo: decidir si la respuesta final está respaldada por esa "
    "evidencia — cifras, fechas y afirmaciones concretas consistentes con "
    "los mensajes de los equipos — o si contiene datos específicos que no "
    "aparecen en ningún mensaje de equipo (señal de alucinación). Marcá "
    "grounded='no' solo cuando haya una afirmación concreta (número, fecha, "
    "hecho puntual) sin respaldo visible en la evidencia; una respuesta que "
    "directamente admite no tener el dato, o que es puramente conversacional "
    "sin cifras, cuenta como grounded='si'."
)


class _GroundednessCheck(TypedDict):
    grounded: str
    reason: str


def output_guardrail_node(state: FinHiveState) -> Command[Literal["__end__"]]:
    """Clasifica si la respuesta final está respaldada por evidencia de las tools."""
    llm = get_chat_model("worker", temperature=0.0)
    structured_llm = llm.with_structured_output(_GroundednessCheck)

    transcript = "\n\n".join(
        f"[{getattr(m, 'name', None) or m.type}]: {m.content}" for m in state["messages"]
    )
    response = structured_llm.invoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ]
    )

    grounded = str(response.get("grounded", "si")).strip().lower() in ("si", "sí", "yes", "true")
    if grounded:
        return Command(goto=END)

    reason = response.get("reason") or "no se encontró evidencia de tools para algunos datos citados"
    warning = (
        "⚠️ Nota de verificación automática: parte de la respuesta anterior "
        f"no pudo respaldarse con evidencia de las tools consultadas ({reason}). "
        "Tratá los datos específicos con cautela y verificalos de forma independiente."
    )
    return Command(
        update={"messages": [AIMessage(content=warning, name="output_guardrail")]},
        goto=END,
    )
