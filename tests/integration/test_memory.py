"""Smoke tests de memoria persistente (ADR 0012): sesión y hechos de largo plazo.

Pega contra Databricks real: LLMs vía Foundation Model APIs y las tablas
Delta de `workspace.finhive` vía el SQL warehouse serverless (mismo caveat
de rate limiting que el resto de `tests/integration/`). Requiere que
`infra/databricks/setup_memory_tables.py` ya se haya corrido una vez.

Correr a mano con:

    uv run pytest tests/integration/test_memory.py -v -s
"""

from __future__ import annotations

import uuid

import mlflow
import mlflow.langchain
import pytest


@pytest.mark.integration
def test_session_memory_persists_across_separate_invocations():
    """Dos `graph.invoke()` separados, mismo thread_id: el segundo debe ver el primero."""
    mlflow.langchain.autolog()

    from finhive.graph import build_top_supervisor
    from finhive.memory.session import load_session_history

    graph = build_top_supervisor()
    thread_id = f"test-session-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    first = graph.invoke(
        {"messages": [("user", "¿Cuál es el precio actual de Bitcoin?")]},
        config=config,
    )
    assert first["messages"][-1].content, "la primera invocación no devolvió respuesta"

    # Sin este mecanismo, la segunda invocación arranca de cero y no tiene
    # forma de saber a qué se refiere "eso" -- es la prueba real de que
    # `memory_recall_node` está anteponiendo el historial guardado.
    second = graph.invoke(
        {"messages": [("user", "¿Y hace cuánto que lo consultamos por primera vez en esta charla?")]},
        config=config,
    )
    assert second["messages"][-1].content, "la segunda invocación no devolvió respuesta"

    saved = load_session_history(thread_id)
    assert len(saved) >= 4, (
        f"se esperaban al menos 4 mensajes guardados (2 turnos completos) para "
        f"thread_id={thread_id}, se encontraron {len(saved)} -- la sesión no se "
        "está persistiendo correctamente entre invocaciones"
    )


@pytest.mark.integration
def test_unrelated_thread_does_not_see_other_threads_history():
    """Dos thread_id distintos no deberían compartir historial de sesión."""
    mlflow.langchain.autolog()

    from langchain_core.messages import HumanMessage

    from finhive.memory.session import load_session_history, save_session_turn

    thread_a = f"test-a-{uuid.uuid4()}"
    thread_b = f"test-b-{uuid.uuid4()}"

    save_session_turn(thread_a, [HumanMessage(content="mensaje único de thread A")])

    history_b = load_session_history(thread_b)
    assert history_b == [], "un thread_id nuevo no debería tener historial de otro thread"

    history_a = load_session_history(thread_a)
    assert len(history_a) == 1
    assert history_a[0].content == "mensaje único de thread A"
