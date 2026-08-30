"""Guardrail de salida: verifica grounding antes de entregar la respuesta final.

Corre una única vez, justo antes del nodo de memoria que cierra el grafo
(`finhive.memory.nodes.memory_remember_node`, ver ADR 0012) — tanto si el
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
    "sin cifras, cuenta como grounded='si'. Si la respuesta menciona nombres, "
    "rankings u otros datos que sí coinciden con la evidencia, aunque no "
    "repita cada cifra exacta de esa evidencia, también cuenta como "
    "grounded='si' — falta de detalle no es lo mismo que alucinación."
)


class _GroundednessCheck(TypedDict):
    grounded: str
    reason: str


def output_guardrail_node(state: FinHiveState) -> Command[Literal["memory_remember"]]:
    """Clasifica si la respuesta final está respaldada por evidencia de las tools.

    Usa el modelo `"supervisor"` (Llama 3.3 70B), no `"worker"` (Llama 3.1
    8B) como el resto de los nodos deterministas de este módulo. Se
    encontró corriendo la evaluación formal (ADR 0013) que el modelo worker
    rechazaba como "no grounded" incluso una coincidencia literal palabra
    por palabra entre respuesta y evidencia, con una razón fabricada — no
    es un problema de prompt, el modelo de 8B no es confiable para esta
    tarea de juicio semántico. Verificado en vivo: el mismo prompt con el
    modelo de 70B juzga ese mismo caso correctamente como grounded.
    """
    llm = get_chat_model("supervisor", temperature=0.0)
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
        return Command(goto="memory_remember")

    reason = response.get("reason") or "no se encontró evidencia de tools para algunos datos citados"
    warning = (
        "\n\n⚠️ Nota de verificación automática: parte de la respuesta anterior "
        f"no pudo respaldarse con evidencia de las tools consultadas ({reason}). "
        "Tratá los datos específicos con cautela y verificalos de forma independiente."
    )
    # Se ANTEPONE la respuesta original al warning en el mismo mensaje -- no
    # se agrega el warning como mensaje aparte. Un warning aparte queda
    # como el último mensaje del state, y cualquier consumidor que lea "el
    # último mensaje" (el propio `finhive.evaluation.run_eval.target`, y el
    # patrón que ya usan los tests de integración) pierde por completo la
    # respuesta real, quedándose solo con el disclaimer y ningún dato. Se
    # encontró corriendo el dataset dorado completo (ADR 0013): ~9 de 13
    # respuestas de dominio quedaban así, con evidencia real de las tools
    # debajo pero invisible para quien solo lee el último mensaje.
    original_answer = str(state["messages"][-1].content)
    return Command(
        update={
            "messages": [AIMessage(content=original_answer + warning, name="output_guardrail")]
        },
        goto="memory_remember",
    )
