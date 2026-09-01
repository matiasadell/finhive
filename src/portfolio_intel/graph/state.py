"""State schema del grafo jerárquico de Portfolio Intel.

Extiende `MessagesState` con `iterations`, el mismo límite duro de
seguridad que usa `top_supervisor.py` para evitar que el supervisor
re-rutee al mismo agente sobre una pregunta ya respondida (mismo hallazgo
real que documentó finhive en su propio `top_supervisor.py`, hoy en
`docs/architecture/adr/finhive-legacy/`). A diferencia de `FinHiveState`, acá
no hay `next` como campo de state aparte (el router lo devuelve vía
`Command`, no hace falta persistirlo) ni ningún campo de memoria de sesión
-- este proyecto no tiene memoria persistente entre invocaciones (ver
`prompts/non_goals.md`), cada corrida analiza el portfolio actual desde cero.
"""

from __future__ import annotations

from langgraph.graph import MessagesState


class PortfolioState(MessagesState):
    iterations: int
