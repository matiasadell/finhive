"""Memoria archival estilo MemGPT: hechos durables entre conversaciones DISTINTAS.

A diferencia de `session.py` (continuidad dentro del mismo `thread_id`), esto
es memoria compartida entre threads — el "archival memory" del patrón MemGPT
(Packer et al., 2023): el sistema decide explícitamente, con el modelo
worker, qué vale la pena recordar más allá de una conversación puntual, y lo
puede recuperar en cualquier conversación futura, no solo la misma.

Simplificación deliberada: `recall_relevant_facts` trae los N hechos más
recientes (sin búsqueda semántica) — no hay todavía un índice de Vector
Search para esto (el de FinHive existe pero sin índices creados, ver
`infra/databricks/README.md`). Para el volumen de hechos que un sistema como
este acumula en una demo, alcanza; recall por similitud semántica es la
extensión natural el día que haya embeddings de por medio (mismo work item
que "RAG estilo RAPTOR" ya listado como trabajo futuro).
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import BaseMessage

from finhive.config.settings import UC_FULL_SCHEMA, get_chat_model
from finhive.memory.store import execute_sql

_TABLE = f"{UC_FULL_SCHEMA}.conversation_facts"

_EXTRACT_PROMPT = (
    "Sos el componente de memoria de largo plazo de FinHive. Te paso el "
    "historial de una conversación de research financiero ya terminada. "
    "Decidí si hay un HECHO DURABLE sobre las preferencias o el contexto del "
    "usuario que valga la pena recordar para conversaciones futuras "
    "completamente distintas — ej. un ticker, sector o tipo de análisis que "
    "pide seguido. NO guardes datos de mercado en sí (precios, tasas, "
    "fechas) — esos quedan viejos y ya están en las tools. Si no hay nada "
    "durable que valga la pena, marcá has_fact='no'."
)


class _FactExtraction(TypedDict):
    has_fact: str
    fact: str


def remember_fact_if_worth_it(thread_id: str, messages: list[BaseMessage]) -> None:
    """Clasifica la conversación con el modelo worker; si hay un hecho durable, lo guarda."""
    llm = get_chat_model("worker", temperature=0.0)
    structured_llm = llm.with_structured_output(_FactExtraction)

    transcript = "\n\n".join(
        f"[{getattr(m, 'name', None) or m.type}]: {m.content}" for m in messages
    )
    response = structured_llm.invoke(
        [
            {"role": "system", "content": _EXTRACT_PROMPT},
            {"role": "user", "content": transcript},
        ]
    )

    has_fact = str(response.get("has_fact", "no")).strip().lower() in ("si", "sí", "yes", "true")
    fact = (response.get("fact") or "").strip()
    if not has_fact or not fact:
        return

    execute_sql(
        f"INSERT INTO {_TABLE} (thread_id, fact, created_at) VALUES (:thread_id, :fact, current_timestamp())",
        {"thread_id": thread_id, "fact": fact},
    )


def recall_relevant_facts(limit: int = 5) -> list[str]:
    """Trae los `limit` hechos durables más recientes guardados, de cualquier thread."""
    rows = execute_sql(f"SELECT fact FROM {_TABLE} ORDER BY created_at DESC LIMIT {int(limit)}")
    return [row[0] for row in rows]
