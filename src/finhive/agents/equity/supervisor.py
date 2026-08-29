"""Sub-supervisor de Equity Research: compone los 3 workers con `langgraph_supervisor`.

Mismo patrón que `finhive.agents.macro.supervisor`.
"""

from __future__ import annotations

from finhive.agents.equity.workers import build_equity_workers
from finhive.config.settings import get_chat_model


def build_equity_supervisor():
    """Compila el grafo del sub-supervisor de Equity Research, listo para invocar."""
    from langgraph_supervisor import create_supervisor

    workers = build_equity_workers()

    supervisor = create_supervisor(
        model=get_chat_model("supervisor"),
        agents=[
            workers["fundamentals_worker"],
            workers["technical_worker"],
            workers["filings_worker"],
        ],
        prompt=(
            "Sos el supervisor del equipo de Equity Research de FinHive. "
            "Coordinás tres analistas: fundamentals_worker (valuación y salud "
            "financiera), technical_worker (precio y tendencia) y "
            "filings_worker (filings de SEC EDGAR). Asigná cada parte de la "
            "pregunta al analista correspondiente, uno a la vez, y después "
            "sintetizá sus respuestas en un análisis de la empresa coherente. "
            "No inventes datos vos mismo — todo dato numérico tiene que venir "
            "de un analista. Este es un sistema de research, no de "
            "asesoramiento financiero: no des recomendaciones de compra/venta."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )
    return supervisor.compile()
