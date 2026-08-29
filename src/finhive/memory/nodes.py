"""Nodos de memoria del grafo: recall antes del supervisor, remember antes de terminar.

Mismo criterio que `finhive.guardrails` (ver ADR 0011): nodos propios de
LangGraph, no tools invocadas por el LLM en medio de una tarea — evita
convertir al supervisor raíz, ya bastante cargado como router, en un agente
de tool-calling además. `memory_recall_node` y `memory_remember_node` son
pasos deterministas del pipeline, uno al principio y otro al final.

El `thread_id` viaja por el `RunnableConfig` estándar de LangGraph
(`config={"configurable": {"thread_id": "..."}}`), no por el `FinHiveState`
— así ninguna invocación existente que no lo pase se rompe, cae a un thread
`"default"` compartido.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import Command

from finhive.graph.state import FinHiveState
from finhive.memory.facts import recall_relevant_facts, remember_fact_if_worth_it
from finhive.memory.session import load_session_history, save_session_turn

_DEFAULT_THREAD_ID = "default"


def _thread_id_from_config(config: RunnableConfig) -> str:
    return ((config or {}).get("configurable") or {}).get("thread_id", _DEFAULT_THREAD_ID)


def memory_recall_node(
    state: FinHiveState, config: RunnableConfig
) -> Command[Literal["supervisor"]]:
    """Antepone el historial guardado del thread y los hechos de largo plazo, si hay.

    `add_messages` (el reducer de `MessagesState`) solo agrega mensajes
    nuevos al final de los que ya hay en el state — no los reordena. Para
    anteponer el historial cargado *antes* del mensaje nuevo del usuario,
    hace falta limpiar el state primero (`RemoveMessage(REMOVE_ALL_MESSAGES)`)
    y reconstruirlo entero en el orden correcto en la misma actualización.
    """
    thread_id = _thread_id_from_config(config)

    history = load_session_history(thread_id)
    facts = recall_relevant_facts()

    new_messages = list(history) + list(state["messages"])
    if facts:
        facts_block = "\n".join(f"- {fact}" for fact in facts)
        new_messages = [
            SystemMessage(
                content=(
                    "Contexto de memoria de largo plazo (de conversaciones "
                    f"previas, puede no ser relevante acá):\n{facts_block}"
                )
            )
        ] + new_messages

    return Command(
        goto="supervisor",
        update={"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + new_messages},
    )


def memory_remember_node(state: FinHiveState, config: RunnableConfig) -> Command[Literal["__end__"]]:
    """Persiste la sesión completa y extrae un hecho durable de largo plazo, si lo hay."""
    from langgraph.graph import END

    thread_id = _thread_id_from_config(config)
    messages = state["messages"]

    save_session_turn(thread_id, messages)
    remember_fact_if_worth_it(thread_id, messages)

    return Command(goto=END)
