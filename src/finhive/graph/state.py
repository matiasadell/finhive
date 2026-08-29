"""State schema compartido por el grafo jerárquico de FinHive.

Extiende `MessagesState` (historial de mensajes) con `next` (el equipo de
dominio al que el top-level supervisor decidió rutear — mismo patrón que la
sección "Hierarchical Agent Teams" del notebook de referencia) y con
`iterations`, un contador de vueltas supervisor→equipo→supervisor usado como
límite duro de seguridad (ver `top_supervisor.py`): sin él, se observó al
supervisor re-rutear al mismo equipo varias veces sobre una pregunta ya
respondida, gastando cuota de requests sin necesidad.
"""

from __future__ import annotations

from langgraph.graph import MessagesState


class FinHiveState(MessagesState):
    next: str
    iterations: int
