"""Memoria de sesión: continuidad de una misma conversación (`thread_id`) entre invocaciones.

No es el checkpointer nativo de LangGraph (`BaseCheckpointSaver`): ese
protocolo versiona el grafo completo en cada paso (pensado para
time-travel/resumir desde cualquier nodo), lo cual implicaría un round-trip
SQL por cada transición del grafo contra la Statement Execution API —
demasiada latencia para algo que acá no hace falta, porque cada
`graph.invoke()` corre de punta a punta en una sola pasada. Esto es más
simple y explícito: guarda/carga la lista completa de mensajes de un thread,
una vez al principio (`load_session_history`) y una vez al final
(`save_session_turn`) de cada invocación — ver ADR 0012.

Sin truncado ni resumen: el historial de un thread crece sin límite. Para
una demo de portfolio no es un problema real, pero es la primera limitación
a resolver si esto se usara con conversaciones largas de verdad.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from finhive.config.settings import UC_FULL_SCHEMA
from finhive.memory.store import execute_sql

_TABLE = f"{UC_FULL_SCHEMA}.conversation_sessions"


def load_session_history(thread_id: str) -> list[BaseMessage]:
    """Carga los mensajes guardados de un thread, en el orden en que se dieron."""
    rows = execute_sql(
        f"""
        SELECT role, msg_name, content FROM {_TABLE}
        WHERE thread_id = :thread_id
        ORDER BY turn_index ASC
        """,
        {"thread_id": thread_id},
    )
    messages: list[BaseMessage] = []
    for role, msg_name, content in rows:
        name = msg_name or None
        if role == "human":
            messages.append(HumanMessage(content=content, name=name))
        else:
            messages.append(AIMessage(content=content, name=name))
    return messages


def save_session_turn(thread_id: str, messages: list[BaseMessage]) -> None:
    """Reemplaza el historial guardado de un thread con la lista completa de mensajes.

    Filtra mensajes `system` (son contexto inyectado por `memory_recall_node`
    en cada corrida, no parte "real" de la conversación — guardarlos los
    duplicaría en cada turno futuro). Hace un DELETE + un único INSERT
    multi-fila en vez de una sentencia por mensaje, para no pagar un
    round-trip HTTP por mensaje contra la Statement Execution API.
    """
    execute_sql(
        f"DELETE FROM {_TABLE} WHERE thread_id = :thread_id",
        {"thread_id": thread_id},
    )

    turns = [m for m in messages if m.type != "system"]
    if not turns:
        return

    values_sql = []
    params: dict[str, str] = {"thread_id": thread_id}
    for index, message in enumerate(turns):
        role = "human" if message.type == "human" else "ai"
        params[f"role{index}"] = role
        params[f"name{index}"] = getattr(message, "name", None) or ""
        params[f"content{index}"] = str(message.content)
        values_sql.append(
            f"(:thread_id, {index}, :role{index}, :name{index}, :content{index}, current_timestamp())"
        )

    execute_sql(
        f"""
        INSERT INTO {_TABLE} (thread_id, turn_index, role, msg_name, content, created_at)
        VALUES {", ".join(values_sql)}
        """,
        params,
    )
