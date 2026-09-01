from __future__ import annotations

from typing import Literal, TypedDict

from langchain_core.messages import AIMessage
from langgraph.graph import END
from langgraph.types import Command

from portfolio_intel.config.settings import get_chat_model
from portfolio_intel.graph.state import PortfolioState

_SYSTEM_PROMPT = (
    "Sos el guardrail de salida de Portfolio Intel. Te paso el historial "
    "completo de una conversación de un sistema multiagente de inteligencia "
    "de portfolio de IA, terminando en una respuesta final. Los mensajes de "
    'los agentes de dominio (etiquetados "<agente>_agent") son la ÚNICA '
    "evidencia real disponible -- vienen de tools deterministas que "
    "calcularon scores/estados/recomendaciones reales sobre los datos del "
    "portfolio.\n\n"
    "Tu trabajo: decidir si la respuesta final está respaldada por esa "
    "evidencia -- ids de casos de uso, scores, value_status, "
    "recomendaciones concretas consistentes con los mensajes de los "
    "agentes -- o si contiene datos específicos que no aparecen en ningún "
    "mensaje de agente (señal de alucinación). Marcá grounded='no' solo "
    "cuando haya una afirmación concreta (score, id, acción recomendada) "
    "sin respaldo visible en la evidencia; una respuesta que admite no "
    "tener el dato, o que es puramente conversacional sin cifras, cuenta "
    "como grounded='si'."
)


class _GroundednessCheck(TypedDict):
    grounded: str
    reason: str


def output_guardrail_node(state: PortfolioState) -> Command[Literal["__end__"]]:
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
        return Command(goto=END)

    reason = response.get("reason") or "no se encontró evidencia de tools para algunos datos citados"
    warning = (
        "\n\n⚠️ Nota de verificación automática: parte de la respuesta anterior "
        f"no pudo respaldarse con evidencia de las tools consultadas ({reason}). "
        "Tratá los datos específicos con cautela y verificalos de forma independiente."
    )
    # El warning se ANTEPONE a la respuesta original en el mismo mensaje, no
    # se agrega aparte -- mismo hallazgo que documentó finhive (ADR 0013
    # archivada): un mensaje de warning solo, al final, hace que cualquier
    # consumidor que lea "el último mensaje" (incluida
    # `evaluation/run_eval.py`) pierda la respuesta real.
    original_answer = str(state["messages"][-1].content)
    return Command(
        update={
            "messages": [AIMessage(content=original_answer + warning, name="output_guardrail")]
        },
        goto=END,
    )
